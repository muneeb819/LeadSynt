"""Ticket service — creation pipeline, listing, status transitions.

Creation pipeline (per architecture): INGESTION -> dedup check -> initial
scoring -> provenance link -> audit -> event. Every step is real and
persisted; nothing is faked.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.company import Company, TicketCompany
from app.models.contact import Contact, TicketContact
from app.models.enums import DuplicateStatus, Freshness, TicketStatus
from app.models.source import Source, TicketSource
from app.models.ticket import Ticket, TicketCategory, TicketStatus as TicketStatusRow, TicketType
from app.queues.events import EventBus
from app.services.audit_service import audit
from app.services.dedup_service import check_duplicates
from app.services.scoring_service import score_ticket

logger = logging.getLogger("leadsynt.tickets")


def _next_reference(db: Session) -> str:
    year_month = datetime.now(timezone.utc).strftime("%Y%m")
    row = db.execute(
        select(func.count()).select_from(Ticket).where(Ticket.reference.like(f"TS-{year_month}-%"))
    ).scalar_one()
    return f"TS-{year_month}-{row + 1:04d}"


def _get_or_create_type(db: Session, code: str, name: str | None) -> TicketType:
    t = db.execute(select(TicketType).where(TicketType.code == code)).scalar_one_or_none()
    if t is None:
        t = TicketType(code=code, name=name or code.replace("_", " ").title())
        db.add(t)
        db.flush()
    return t


def _get_or_create_company(
    db: Session, *, legal_name: str | None = None, domain: str | None = None, website: str | None = None
) -> Company | None:
    if not legal_name and not domain:
        return None
    company = None
    if domain:
        company = db.execute(select(Company).where(Company.domain == domain.lower())).scalar_one_or_none()
    if company is None and legal_name:
        company = db.execute(
            select(Company).where(func.lower(Company.legal_name) == legal_name.lower())
        ).scalar_one_or_none()
    if company is None:
        company = Company(
            legal_name=legal_name or (domain or "unknown").title(),
            domain=domain.lower() if domain else None,
            website=website,
        )
        db.add(company)
        db.flush()
    else:
        if website and not company.website:
            company.website = website
        if domain and not company.domain:
            company.domain = domain.lower()
    return company


def _get_or_create_contact(
    db: Session,
    *,
    full_name: str | None = None,
    title: str | None = None,
    work_email: str | None = None,
    phone: str | None = None,
    profile_url: str | None = None,
    company: Company | None = None,
) -> Contact | None:
    if not full_name and not work_email:
        return None
    contact = None
    if work_email:
        contact = db.execute(
            select(Contact).where(func.lower(Contact.work_email) == work_email.lower())
        ).scalar_one_or_none()
    if contact is None and full_name:
        contact = db.execute(
            select(Contact).where(func.lower(Contact.full_name) == full_name.lower())
        ).scalar_one_or_none()
    if contact is None:
        contact = Contact(
            full_name=full_name or "Unknown",
            title=title,
            work_email=work_email,
            phone=phone,
            profile_url=profile_url,
            company_id=company.id if company else None,
        )
        db.add(contact)
        db.flush()
    return contact


def create_ticket(
    db: Session,
    *,
    data: dict,
    actor_id: str | None = None,
    actor_type: str = "system",
) -> Ticket:
    """Create a ticket with full pipeline: dedup, scoring, provenance, audit."""
    now = datetime.now(timezone.utc)

    from app.models.enums import IntentLevel

    ttype = _get_or_create_type(db, data.get("type_code", "GENERAL"), data.get("type_name", "General"))
    status_row = db.execute(
        select(TicketStatusRow).where(TicketStatusRow.code == TicketStatus.INGESTED.value)
    ).scalar_one()

    ticket = Ticket(
        reference=_next_reference(db),
        type_id=ttype.id,
        status_id=status_row.id,
        category_id=data.get("category_id"),
        domain=data.get("domain"),
        market_sector=data.get("market_sector"),
        product=data.get("product"),
        service=data.get("service"),
        requirement=data.get("requirement"),
        requirement_details=data.get("requirement_details") or {},
        intent_level=IntentLevel(data["intent_level"]) if data.get("intent_level") else None,
        urgency=data.get("urgency"),
        budget=data.get("budget"),
        currency=data.get("currency"),
        deal_size=data.get("deal_size"),
        location=data.get("location"),
        jurisdiction=data.get("jurisdiction"),
        timezone=data.get("timezone"),
        pain_point=data.get("pain_point"),
        platform=data.get("platform"),
        platform_url=data.get("platform_url"),
        original_url=data.get("original_url"),
        official_website_url=data.get("official_website_url"),
        discovered_at=data.get("discovered_at") or now,
        published_at=data.get("published_at"),
        discovered_by=data.get("discovered_by") or "manual",
        owner_id=data.get("owner_id") or actor_id,
        notes=data.get("notes"),
        last_activity_at=now,
    )
    db.add(ticket)
    db.flush()

    # Attachments (contacts / companies) with provenance links.
    company = None
    if data.get("company"):
        company = _get_or_create_company(db, **data["company"])
        if company:
            db.add(TicketCompany(ticket_id=ticket.id, company_id=company.id))
    contact = None
    if data.get("contact"):
        contact = _get_or_create_contact(db, company=company, **data["contact"])
        if contact:
            db.add(TicketContact(ticket_id=ticket.id, contact_id=contact.id, role=data.get("contact_role", "PRIMARY")))

    # Provenance link to the source (mandatory when known).
    if data.get("source_id"):
        src = db.get(Source, data["source_id"])
        if src:
            db.add(TicketSource(ticket_id=ticket.id, source_id=src.id, url=data.get("original_url"), captured_at=now))
            ticket.platform = ticket.platform or src.platform or src.name
            ticket.platform_url = ticket.platform_url or src.base_url

    db.flush()

    # Dedup detection (explainable, recorded).
    dedup = check_duplicates(db, ticket)
    ticket.duplicate_status = dedup.status

    # Initial scoring (deterministic rule engine).
    score_ticket(db, ticket, computed_by=data.get("computed_by", "rule-engine"))

    audit(
        db,
        action="ticket.created",
        actor_id=actor_id,
        actor_type=actor_type,
        resource_type="ticket",
        resource_id=ticket.id,
        after={"reference": ticket.reference, "type": ttype.code, "duplicate_status": dedup.status.value,
               "lead_score": ticket.lead_score},
        meta={"dedup_reason": dedup.reason},
    )
    EventBus.publish("ticket.created", {"ticket_id": ticket.id, "reference": ticket.reference})
    db.flush()
    return ticket


def get_ticket(db: Session, ticket_id: str, *, include_relations: bool = True) -> Ticket:
    q = select(Ticket).where(Ticket.id == ticket_id)
    if include_relations:
        q = q.options(
            joinedload(Ticket.type),
            joinedload(Ticket.status),
            joinedload(Ticket.category),
            joinedload(Ticket.ticket_contacts).joinedload(TicketContact.contact),
            joinedload(Ticket.ticket_companies).joinedload(TicketCompany.company),
            joinedload(Ticket.ticket_sources),
        )
    ticket = db.execute(q).scalars().first()
    if ticket is None:
        raise NotFoundError("Ticket not found", details={"ticket_id": ticket_id})
    return ticket


def list_tickets(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    type_code: str | None = None,
    category_code: str | None = None,
    verification: str | None = None,
    duplicate_status: str | None = None,
    owner_id: str | None = None,
    market_sector: str | None = None,
    q: str | None = None,
    sort: str = "-created_at",
) -> tuple[list[Ticket], int]:
    filters = [Ticket.is_archived.is_(False)]
    if status:
        filters.append(
            Ticket.status_id.in_(
                select(TicketStatusRow.id).where(TicketStatusRow.code == status.upper())
            )
        )
    if type_code:
        filters.append(Ticket.type_id.in_(select(TicketType.id).where(TicketType.code == type_code.upper())))
    if category_code:
        filters.append(Ticket.category_id.in_(select(TicketCategory.id).where(TicketCategory.code == category_code.upper())))
    if verification:
        from app.models.enums import VerificationStatus

        filters.append(Ticket.verification_status == VerificationStatus(verification.upper()))
    if duplicate_status:
        from app.models.enums import DuplicateStatus as DS

        filters.append(Ticket.duplicate_status == DS(duplicate_status.upper()))
    if owner_id:
        filters.append(Ticket.owner_id == owner_id)
    if market_sector:
        filters.append(Ticket.market_sector == market_sector)
    if q:
        like = f"%{q}%"
        filters.append(
            or_(
                Ticket.reference.ilike(like),
                Ticket.product.ilike(like),
                Ticket.requirement.ilike(like),
                Ticket.location.ilike(like),
                Ticket.platform.ilike(like),
            )
        )

    desc = sort.startswith("-")
    col_name = sort.lstrip("-")
    col = getattr(Ticket, col_name, None)
    if col is None:
        col, desc = Ticket.created_at, True
    total = db.execute(select(func.count()).select_from(Ticket).where(*filters)).scalar_one()
    items = list(
        db.execute(
            select(Ticket)
            .options(joinedload(Ticket.type), joinedload(Ticket.status), joinedload(Ticket.category))
            .where(*filters)
            .order_by(col.desc() if desc else col.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return items, total


def transition_status(
    db: Session,
    ticket: Ticket,
    *,
    to_status: TicketStatus,
    actor_id: str | None = None,
    reason: str | None = None,
) -> Ticket:
    """Controlled status change through the state machine (audited)."""
    from app.services.ticket_status_machine import assert_transition

    status_row = db.get(TicketStatusRow, ticket.status_id)
    current = TicketStatus(status_row.code)
    if current is to_status:
        raise BadRequestError("Ticket is already in that status",
                              code="no_status_change", details={"status": current.value})
    assert_transition(current, to_status)
    new_row = db.execute(
        select(TicketStatusRow).where(TicketStatusRow.code == to_status.value)
    ).scalar_one()
    before = {"status": current.value}
    ticket.status_id = new_row.id
    ticket.status = new_row  # keep the relationship cache in sync
    ticket.last_activity_at = datetime.now(timezone.utc)
    audit(
        db,
        action="ticket.status_changed",
        actor_id=actor_id,
        actor_type="user" if actor_id else "system",
        resource_type="ticket",
        resource_id=ticket.id,
        before=before,
        after={"status": to_status.value},
        meta={"reason": reason},
    )
    EventBus.publish("ticket.updated", {"ticket_id": ticket.id, "status": to_status.value})
    db.flush()
    return ticket


def update_ticket(
    db: Session,
    ticket: Ticket,
    *,
    data: dict,
    actor_id: str | None = None,
) -> Ticket:
    """Partial update with before/after audit. Unknown keys ignored."""
    allowed = {
        "domain", "market_sector", "product", "service", "requirement",
        "requirement_details", "intent_level", "urgency", "budget", "currency",
        "deal_size", "location", "jurisdiction", "timezone", "pain_point",
        "notes", "owner_id", "platform", "platform_url", "original_url",
        "official_website_url",
    }
    from app.models.enums import IntentLevel

    before: dict = {}
    for key, value in data.items():
        if key not in allowed or value is None:
            continue
        before[key] = getattr(ticket, key)
        if key == "intent_level":
            value = IntentLevel(value)
        setattr(ticket, key, value)
    if before:
        ticket.last_activity_at = datetime.now(timezone.utc)
        audit(
            db,
            action="ticket.updated",
            actor_id=actor_id,
            actor_type="user" if actor_id else "system",
            resource_type="ticket",
            resource_id=ticket.id,
            before=before,
            after=dict(data),
        )
        EventBus.publish("ticket.updated", {"ticket_id": ticket.id})
        db.flush()
    return ticket


def archive_ticket(db: Session, ticket: Ticket, *, actor_id: str | None = None) -> Ticket:
    ticket.is_archived = True
    ticket.last_activity_at = datetime.now(timezone.utc)
    audit(
        db, action="ticket.archived", actor_id=actor_id,
        actor_type="user" if actor_id else "system",
        resource_type="ticket", resource_id=ticket.id,
    )
    db.flush()
    return ticket


def refresh_freshness(db: Session, *, stale_hours: int = 168, aging_hours: int = 72) -> int:
    """Mark tickets FRESH/AGING/STALE by discovery age. Returns count changed."""
    now = datetime.now(timezone.utc)
    changed = 0
    for ticket in db.execute(select(Ticket).where(Ticket.is_archived.is_(False))).scalars():
        if ticket.discovered_at is None:
            continue
        age_h = (now - ticket.discovered_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        new = (
            Freshness.FRESH if age_h <= aging_hours
            else Freshness.AGING if age_h <= stale_hours
            else Freshness.STALE
        )
        if ticket.freshness != new:
            ticket.freshness = new
            changed += 1
    if changed:
        db.flush()
    return changed
