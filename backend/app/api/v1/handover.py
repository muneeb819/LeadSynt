"""Handover API: dossier + conversation history for a ticket."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import NotFoundError
from app.models.conversation import Conversation
from app.models.ops import AuditLog
from app.models.ticket import Ticket
from app.schemas.common import Envelope

router = APIRouter()


@router.get("/{ticket_id}/dossier", response_model=Envelope)
def dossier(
    ticket_id: str,
    user=Depends(require_permission("tickets:read")),
    db: Session = Depends(get_db),
):
    if db.get(Ticket, ticket_id) is None:
        raise NotFoundError("Ticket not found")
    events = db.execute(
        select(AuditLog)
        .where(AuditLog.resource_id == ticket_id, AuditLog.action.in_(
            ["handover.created", "outreach.automation_paused"]))
        .order_by(AuditLog.timestamp.desc())
    ).scalars().all()
    conv = db.execute(
        select(Conversation).where(Conversation.ticket_id == ticket_id)
    ).scalars().first()
    messages = [
        {
            "direction": m.direction, "sender": m.sender, "content": m.content,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        }
        for m in (conv.messages if conv else [])
    ]
    latest_handover = next((e for e in events if e.action == "handover.created"), None)
    return Envelope(data={
        "ticket_id": ticket_id,
        "handover": latest_handover.after if latest_handover else None,
        "automation_paused": any(e.action == "outreach.automation_paused" for e in events),
        "conversation": messages,
    })
