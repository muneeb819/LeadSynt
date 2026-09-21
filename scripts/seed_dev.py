"""Development seed (IDEMPOTENT).

Creates: RBAC + agent registry + status registry (also done at app startup),
three dev users, the authorized dev source + connector, and real pipeline
data by RUNNING the dev feed connector (discovery -> source records ->
tickets -> dedup -> scoring). A subset of tickets is advanced through the
controlled status machine, verified, and handed to owners.

Run from anywhere:  cd backend && .venv/bin/python ../scripts/seed_dev.py
Never runs in production (refuses when LEADSynt_ENVIRONMENT=production).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.core.database import Base, SessionLocal, build_engine, reset_engine  # noqa: E402
import app.models  # noqa: E402,F401

settings = get_settings()


def _users(db) -> dict[str, object]:
    from sqlalchemy import select

    from app.auth.rbac import ensure_rbac_seeded
    from app.core.security import hash_password
    from app.models.user import Role, User, UserRole

    ensure_rbac_seeded(db)
    creds = {
        "admin": (settings.seed_admin_email, "admin@leadsynt.io", settings.seed_admin_password, "admin"),
        "operator": ("operator@leadsynt.io", "operator@leadsynt.io", "LeadSynt-Dev-Only-2026", "operator"),
        "viewer": ("viewer@leadsynt.io", "viewer@leadsynt.io", "LeadSynt-Dev-Only-2026", "viewer"),
    }
    out = {}
    for key, (email, _label, password, role_name) in creds.items():
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            user = User(email=email, full_name=key.capitalize() + " User",
                        password_hash=hash_password(password))
            db.add(user)
            db.flush()
        if not user.user_roles:
            role = db.execute(select(Role).where(Role.name == role_name)).scalar_one()
            db.add(UserRole(user_id=user.id, role_id=role.id))
            db.flush()
        out[key] = user
    return out


def _source_and_connector(db) -> tuple[object, object]:
    from sqlalchemy import select

    from app.models.enums import AuthMethod, ConnectorHealth, SourceKind
    from app.models.source import Source, SourceConnector

    src = db.execute(select(Source).where(Source.name == "Approved Dev Marketplace Feed")).scalar_one_or_none()
    if src is None:
        src = Source(
            name="Approved Dev Marketplace Feed",
            platform="dev-marketplace",
            kind=SourceKind.FEED,
            base_url="https://devmarket.example.com/feed",
            description="Explicitly authorized local development feed (synthetic data).",
            compliance_notes="Authorized dev dataset. No scraping, no bypasses, synthetic content only.",
        )
        db.add(src)
        db.flush()
    conn = db.execute(select(SourceConnector).where(SourceConnector.connector_id == "dev_feed")).scalar_one_or_none()
    if conn is None:
        conn = SourceConnector(
            connector_id="dev_feed",
            source_id=src.id,
            status="ACTIVE",
            auth_method=AuthMethod.NONE,
            schedule_cron="0 */6 * * *",
            rate_limit_per_hour=10,
            health=ConnectorHealth.HEALTHY,
            configuration={"feed_path": "database/dev_feed.json", "channel": "authorized_local_file"},
        )
        db.add(conn)
        db.flush()
    return src, conn


def _advance(db, ticket, path: list[str], owner=None) -> None:
    """Walk a ticket through the state machine (valid transitions only)."""
    from app.models.enums import TicketStatus
    from app.services.ticket_service import transition_status

    current = TicketStatus(ticket.status.code)
    for code in path:
        target = TicketStatus(code)
        if current is target:
            continue
        transition_status(db, ticket, to_status=target, actor_id=None, reason="dev seed")
        current = target
    if owner is not None:
        ticket.owner_id = owner.id


def main() -> None:
    if settings.is_production:
        print("Refusing to seed in production.")
        sys.exit(1)

    # Fresh schema if missing (dev convenience; migrations are the source of truth).
    from sqlalchemy import inspect as sa_inspect

    engine = build_engine()
    if not sa_inspect(engine).has_table("users"):
        print("Creating base schema for dev database...")
        Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        # Registries
        from sqlalchemy import select

        from app.agents.registry import ensure_agents_seeded
        from app.auth.rbac import ensure_rbac_seeded
        from app.configuration import ensure_defaults
        from app.models.enums import TicketStatus
        from app.models.ticket import TicketStatus as TicketStatusRow

        ensure_rbac_seeded(db)
        ensure_agents_seeded(db)
        ensure_defaults(db)
        have = {r.code for r in db.execute(select(TicketStatusRow)).scalars()}
        for st in TicketStatus:
            if st.value not in have:
                db.add(TicketStatusRow(
                    code=st.value, name=st.value.replace("_", " ").title(),
                    is_terminal=st in {TicketStatus.WON, TicketStatus.LOST,
                                       TicketStatus.DISQUALIFIED, TicketStatus.DUPLICATE,
                                       TicketStatus.EXPIRED, TicketStatus.ARCHIVED},
                ))
        db.commit()

        users = _users(db)

        from app.models.ticket import Ticket
        existing_tickets = db.execute(select(Ticket).limit(1)).scalars().first()

        if existing_tickets is None:
            # RUN the real pipeline: connector fetch -> records -> tickets.
            from app.connectors.dev_feed import DevFeedConnector
            from app.models.source import SourceRecord
            from sqlalchemy import select as _sel

            src, conn = _source_and_connector(db)
            runner = DevFeedConnector(db, conn)
            run = runner.run(trigger="seed")
            rows = db.execute(_sel(SourceRecord).where(
                SourceRecord.source_id == src.id, SourceRecord.is_consumed == False
            )).scalars().all()
            raw = [
                __import__("app.connectors.base", fromlist=["RawRecord"]).RawRecord(
                    external_id=r.external_id or "", url=r.url, payload=r.payload,
                    captured_at=r.captured_at,
                )
                for r in rows
            ]
            created = runner.materialize(raw)
            run.tickets_created = created
            db.commit()
            print(f"Pipeline run: connector={run.status.value}, tickets_created={created}")
        else:
            print("Tickets already present — skipping pipeline seed (idempotent).")
            src, conn = _source_and_connector(db)

        # Advance a deterministic subset through the machine + verify + assign.
        tickets = list(db.execute(select(Ticket).order_by(Ticket.reference)).scalars().all())
        if tickets:
            from app.services.verification_service import verify_company, verify_email_address
            from app.models.contact import Contact, TicketContact
            from app.models.company import Company, TicketCompany
            from sqlalchemy import select as _sel

            plans = [
                (0, ["PROCESSING", "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED",
                     "OUTREACH_READY", "OUTREACH_ACTIVE"], "admin"),
                (1, ["PROCESSING", "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED",
                     "OUTREACH_READY", "OUTREACH_ACTIVE"], "operator"),
                (2, ["PROCESSING", "VERIFICATION_PENDING"], "operator"),
                (3, ["PROCESSING", "REVIEW_REQUIRED"], "admin"),
                (4, ["PROCESSING", "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED"], "operator"),
                (5, ["PROCESSING"], "viewer"),
                (6, ["PROCESSING", "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED",
                     "OUTREACH_READY", "OUTREACH_ACTIVE", "REPLIED"], "operator"),
                (7, ["PROCESSING", "REVIEW_REQUIRED", "VERIFICATION_PENDING", "VERIFIED",
                     "QUALIFIED", "OUTREACH_READY"], "admin"),
            ]
            for idx, path, owner_key in plans:
                if idx >= len(tickets):
                    continue
                t = tickets[idx]
                if t.is_archived:
                    continue
                _advance(db, t, path, owner=users[owner_key])
                # Verify first two tickets' emails + company (real service calls).
                if idx in (0, 1, 6):
                    crow = db.execute(_sel(Contact).join(
                        TicketContact, TicketContact.contact_id == Contact.id
                    ).where(TicketContact.ticket_id == t.id)).scalars().first()
                    if crow and crow.work_email:
                        verify_email_address(db, email=crow.work_email, ticket_id=t.id)
                    crow2 = db.execute(_sel(Company).join(
                        TicketCompany, TicketCompany.company_id == Company.id
                    ).where(TicketCompany.ticket_id == t.id)).scalars().first()
                    if crow2:
                        verify_company(db, company_id=crow2.id, ticket_id=t.id)

            # Simulate a qualifying reply on ticket idx=6 (REPLIED via handover).
            replied = tickets[6]
            if replied.status.code == "REPLIED" and not db.execute(_sel(__import__("app.models.conversation", fromlist=["ConversationMessage"]).ConversationMessage).limit(1)).scalars().first():
                pass  # already recorded via transition; dossier created on webhook path

            # Suppression + consent samples (privacy guardrails).
            from app.models.ops import SuppressionRecord, ConsentRecord
            from app.models.contact import Contact as C

            if db.execute(_sel(SuppressionRecord).limit(1)).scalars().first() is None:
                db.add(SuppressionRecord(
                    scope="email", value="optout@example.com",
                    reason="opt_out", source="dev-seed",
                ))
                first_contact = db.execute(_sel(C).limit(1)).scalars().first()
                if first_contact:
                    db.add(ConsentRecord(contact_id=first_contact.id,
                                         purpose="outreach_email", status="GRANTED",
                                         source="dev-seed"))
            # Stale ticket: backdate one ticket's discovery to trigger QA sweep.
            if len(tickets) > 8:
                stale = tickets[8]
                if stale.discovered_at is None:
                    stale.discovered_at = datetime.now(timezone.utc) - timedelta(days=45)

        # Notifications for owners (in-app).
        from app.models.enums import NotificationType
        from app.services.notification_service import notify

        admin = users["admin"]
        if not db.execute(_sel(__import__("app.models.ops", fromlist=["Notification"]).Notification).limit(1)).scalars().first():
            notify(db, user_id=admin.id, type=NotificationType.SYSTEM,
                   title="Welcome to LeadSynt",
                   body="Foundation seeded. Explore the Control Center.")
            notify(db, user_id=admin.id, type=NotificationType.TICKET_UPDATE,
                   title="Pipeline complete",
                   body="Dev feed connector ingested the first batch of tickets.")

        db.commit()

        print("\n=== LeadSynt dev seed complete ===")
        print(f"users: admin={settings.seed_admin_email} / {settings.seed_admin_password}")
        print("       operator@leadsynt.io / LeadSynt-Dev-Only-2026")
        print("       viewer@leadsynt.io   / LeadSynt-Dev-Only-2026")
        n = len(db.execute(select(Ticket)).scalars().all())
        print(f"tickets: {n}")
        print("NOTE: dev credentials are for local development only.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
