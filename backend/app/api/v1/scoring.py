"""Scoring API: snapshot history per ticket."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import NotFoundError
from app.models.scoring import IntentScoreSnapshot, LeadScoreSnapshot, RiskScoreSnapshot
from app.models.ticket import Ticket
from app.schemas.common import Envelope

router = APIRouter()


@router.get("/snapshots/{ticket_id}", response_model=Envelope)
def snapshots(
    ticket_id: str,
    user=Depends(require_permission("tickets:read")),
    db: Session = Depends(get_db),
):
    if db.get(Ticket, ticket_id) is None:
        raise NotFoundError("Ticket not found")
    out = []
    for model, label in ((LeadScoreSnapshot, "lead"), (IntentScoreSnapshot, "intent"),
                         (RiskScoreSnapshot, "risk")):
        rows = db.execute(
            select(model).where(model.ticket_id == ticket_id)
            .order_by(model.created_at.desc()).limit(10)
        ).scalars().all()
        out.extend({
            "kind": label, "score": r.score, "confidence": float(r.confidence) if r.confidence is not None else None,
            "factors": r.factors, "computed_by": r.computed_by,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        } for r in rows)
    return Envelope(data=out)
