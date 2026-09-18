"""Suppression / opt-out enforcement (privacy guardrail).

Automated outreach MUST check suppression before sending. Suppressions with
a future ``expires_at`` are auto-ignored after expiry; permanent ones never
expire.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import SuppressedContactError
from app.models.ops import SuppressionRecord
from app.models.contact import Contact


def is_suppressed(
    db: Session,
    *,
    email: str | None = None,
    phone: str | None = None,
    contact_id: str | None = None,
) -> bool:
    now = datetime.now(timezone.utc)
    clauses = [SuppressionRecord.expires_at.is_(None)]
    if email:
        clauses.append(SuppressionRecord.value == email.lower().strip())
    if phone:
        clauses.append(SuppressionRecord.value == phone.strip())
    if contact_id:
        clauses.append(SuppressionRecord.contact_id == contact_id)
    row = db.execute(
        select(SuppressionRecord.id)
        .where(or_(*clauses) & SuppressionRecord.expires_at.is_(None))
        .limit(1)
    ).first()
    if row:
        return True
    # expired rows don't suppress
    return False


def check_outreach_allowed(db: Session, contact: Contact) -> None:
    if is_suppressed(
        db,
        email=contact.work_email,
        phone=contact.phone,
        contact_id=contact.id,
    ):
        raise SuppressedContactError(
            f"Contact {contact.id} is suppressed (DO-NOT-CONTACT); outreach is blocked",
            details={"contact_id": contact.id},
        )


def add_suppression(
    db: Session,
    *,
    scope: str,
    value: str,
    contact_id: str | None = None,
    reason: str | None = None,
    source: str | None = None,
    expires_at: datetime | None = None,
) -> SuppressionRecord:
    rec = SuppressionRecord(
        scope=scope,
        value=value.lower().strip() if scope == "email" else value.strip(),
        contact_id=contact_id,
        reason=reason,
        source=source,
        expires_at=expires_at,
    )
    db.add(rec)
    db.flush()
    return rec
