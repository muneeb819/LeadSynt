"""Leads API — qualified-ticket view (subset of the tickets domain)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.schemas.common import Envelope
from app.schemas.ticket import TicketOut
from app.services.ticket_service import list_tickets

router = APIRouter()

LEAD_STATUSES = (
    "QUALIFIED", "OUTREACH_READY", "OUTREACH_ACTIVE", "REPLIED", "HOT_LEAD",
    "AWAITING_HUMAN", "MEETING_BOOKED", "NEGOTIATION", "PROPOSAL_SENT",
)


@router.get("", response_model=Envelope)
def leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    min_score: int = Query(0, ge=0, le=100),
    status: str | None = None,
    q: str | None = Query(None, max_length=120),
    user=Depends(require_permission("leads:read")),
    db: Session = Depends(get_db),
):
    # Foundation: leads = tickets in lead-zone statuses, sorted by lead score.
    items: list = []
    total = 0
    for st in (status.upper(),) if status else LEAD_STATUSES:
        chunk, _ = list_tickets(db, page=1, page_size=500, status=st, q=q, sort="-lead_score")
        items.extend(chunk)
    if min_score > 0:
        items = [t for t in items if (t.lead_score or 0) >= min_score]
    items.sort(key=lambda t: (t.lead_score or 0), reverse=True)
    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start:start + page_size]
    return Envelope(data={
        "items": [TicketOut.from_ticket(t).model_dump() for t in page_items],
        "pagination": {
            "page": page, "page_size": page_size, "total": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    })
