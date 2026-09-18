"""Duplicate detection — deterministic and explainable.

Rules (in priority order):
1. Same primary work email AND same primary company domain  -> DUPLICATE
2. Same primary work email                                   -> POSSIBLE_DUPLICATE
3. Same company domain AND same market sector + product      -> POSSIBLE_DUPLICATE

Unknowns are never guessed: missing email/domain simply skip that rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.enums import DuplicateStatus
from app.models.ticket import Ticket
from app.core.database import Base  # noqa: F401  (import side-effect: models)

# Ensure models are imported so their tables exist.
import app.models  # noqa: E402,F401


@dataclass(frozen=True, slots=True)
class DedupResult:
    status: DuplicateStatus
    matched_ticket_id: str | None
    matched_reference: str | None
    reason: str


def _primary_email(db: Session, ticket_id: str) -> str | None:
    from app.models.contact import Contact, TicketContact

    row = db.execute(
        select(Contact.work_email)
        .join(TicketContact, TicketContact.contact_id == Contact.id)
        .where(TicketContact.ticket_id == ticket_id)
        .order_by(TicketContact.id)
        .limit(1)
    ).first()
    return row[0] if row else None


def _primary_domain(db: Session, ticket_id: str) -> str | None:
    from app.models.company import Company, TicketCompany

    row = db.execute(
        select(Company.domain)
        .join(TicketCompany, TicketCompany.company_id == Company.id)
        .where(TicketCompany.ticket_id == ticket_id)
        .order_by(TicketCompany.id)
        .limit(1)
    ).first()
    return row[0] if row else None


def check_duplicates(db: Session, ticket: Ticket) -> DedupResult:
    """Compare ``ticket`` against existing tickets. Does not mutate state;
    callers persist the resulting status."""
    my_email = (_primary_email(db, ticket.id) or "").lower().strip() or None
    my_domain = (_primary_domain(db, ticket.id) or "").lower().strip() or None

    candidates = db.execute(
        select(Ticket)
        .options(joinedload(Ticket.type))
        .where(Ticket.id != ticket.id, Ticket.is_archived.is_(False))
    ).scalars().all()

    for cand in candidates:
        if cand.duplicate_status in (DuplicateStatus.DUPLICATE, DuplicateStatus.MERGED):
            continue
        cand_email = (_primary_email(db, cand.id) or "").lower().strip() or None
        cand_domain = (_primary_domain(db, cand.id) or "").lower().strip() or None

        if my_email and cand_email and my_email == cand_email:
            if my_domain and cand_domain and my_domain == cand_domain:
                return DedupResult(
                    DuplicateStatus.DUPLICATE, cand.id, cand.reference,
                    f"same primary email and company domain as {cand.reference}",
                )
            return DedupResult(
                DuplicateStatus.POSSIBLE_DUPLICATE, cand.id, cand.reference,
                f"same primary email as {cand.reference}",
            )
        if (
            my_domain and cand_domain and my_domain == cand_domain
            and (ticket.product or "").lower() == (cand.product or "").lower()
            and ticket.product
            and (ticket.market_sector or "") == (cand.market_sector or "")
        ):
            return DedupResult(
                DuplicateStatus.POSSIBLE_DUPLICATE, cand.id, cand.reference,
                f"same company domain, sector and product as {cand.reference}",
            )
    return DedupResult(DuplicateStatus.UNIQUE, None, None, "no matches found")
