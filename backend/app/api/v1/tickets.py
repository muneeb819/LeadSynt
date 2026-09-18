"""Tickets API — the central object."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.enums import TicketStatus
from app.schemas.common import Envelope
from app.schemas.ticket import (
    ScoreOut, StatusTransitionIn, TicketCreateIn, TicketOut, TicketUpdateIn,
    VerificationRecordOut,
)
from app.services.scoring_service import score_ticket
from app.services.ticket_service import (
    archive_ticket, create_ticket, get_ticket, list_tickets, transition_status,
    update_ticket,
)
from app.services.verification_service import ticket_verification_history

router = APIRouter()


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.get("", response_model=Envelope)
def tickets(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = None,
    type_code: str | None = None,
    category: str | None = None,
    verification: str | None = None,
    duplicate_status: str | None = None,
    owner_id: str | None = None,
    market_sector: str | None = None,
    q: str | None = Query(None, max_length=120),
    sort: str = Query("-created_at", max_length=40),
    user=Depends(require_permission("tickets:read")),
    db: Session = Depends(get_db),
):
    items, total = list_tickets(
        db, page=page, page_size=page_size, status=status, type_code=type_code,
        category_code=category, verification=verification,
        duplicate_status=duplicate_status, owner_id=owner_id,
        market_sector=market_sector, q=q, sort=sort,
    )
    from app.core.pagination import PageResult

    result = PageResult(items=[TicketOut.from_ticket(t).model_dump() for t in items],
                        page=page, page_size=page_size, total=total,
                        total_pages=(total + page_size - 1) // page_size)
    return Envelope(data=result.to_envelope(), request_id=_request_id(request))


@router.post("", status_code=201, response_model=Envelope)
def create(
    payload: TicketCreateIn,
    request: Request,
    user=Depends(require_permission("tickets:write")),
    db: Session = Depends(get_db),
):
    data = payload.model_dump()
    if "budget" in data and data["budget"] is not None:
        data["budget"] = float(data["budget"])
    ticket = create_ticket(db, data=data, actor_id=user.id, actor_type="user")
    db.commit()
    return Envelope(data=TicketOut.from_ticket(ticket).model_dump(), request_id=_request_id(request))


@router.get("/{ticket_id}", response_model=Envelope)
def detail(
    ticket_id: str,
    request: Request,
    user=Depends(require_permission("tickets:read")),
    db: Session = Depends(get_db),
):
    ticket = get_ticket(db, ticket_id)
    data = TicketOut.from_ticket(ticket).model_dump()
    data["verification_history"] = [
        VerificationRecordOut.model_validate(r).model_dump()
        for r in ticket_verification_history(db, ticket_id)
    ]
    return Envelope(data=data, request_id=_request_id(request))


@router.patch("/{ticket_id}", response_model=Envelope)
def update(
    ticket_id: str,
    payload: TicketUpdateIn,
    request: Request,
    user=Depends(require_permission("tickets:write")),
    db: Session = Depends(get_db),
):
    ticket = get_ticket(db, ticket_id)
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    if "budget" in data and data["budget"] is not None:
        data["budget"] = float(data["budget"])
    update_ticket(db, ticket, data=data, actor_id=user.id)
    db.commit()
    return Envelope(data=TicketOut.from_ticket(get_ticket(db, ticket_id)).model_dump(),
                    request_id=_request_id(request))


@router.post("/{ticket_id}/status", response_model=Envelope)
def transition(
    ticket_id: str,
    payload: StatusTransitionIn,
    request: Request,
    user=Depends(require_permission("tickets:transition")),
    db: Session = Depends(get_db),
):
    ticket = get_ticket(db, ticket_id)
    try:
        to_status = TicketStatus(payload.status.upper())
    except ValueError:
        raise BadRequestError(f"Unknown status: {payload.status}")
    transition_status(db, ticket, to_status=to_status, actor_id=user.id, reason=payload.reason)
    db.commit()
    return Envelope(data=TicketOut.from_ticket(ticket).model_dump(), request_id=_request_id(request))


@router.post("/{ticket_id}/score", response_model=Envelope)
def score(
    ticket_id: str,
    request: Request,
    user=Depends(require_permission("scoring:run")),
    db: Session = Depends(get_db),
):
    ticket = get_ticket(db, ticket_id)
    result = score_ticket(db, ticket)
    db.commit()
    return Envelope(
        data=ScoreOut(
            lead=result["lead"], intent=result["intent"], risk=result["risk"],
            confidence=result["confidence"], factors=result["factors"],
        ).model_dump(),
        request_id=_request_id(request),
    )


@router.post("/{ticket_id}/archive", response_model=Envelope)
def archive(
    ticket_id: str,
    request: Request,
    user=Depends(require_permission("tickets:delete")),
    db: Session = Depends(get_db),
):
    ticket = get_ticket(db, ticket_id)
    archive_ticket(db, ticket, actor_id=user.id)
    db.commit()
    return Envelope(data={"id": ticket.id, "archived": True}, request_id=_request_id(request))
