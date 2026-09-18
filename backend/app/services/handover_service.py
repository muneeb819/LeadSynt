"""CRITICAL reply-handover rule (spec §16).

When a prospect replies:
1. Record the exact incoming message (conversation history).
2. Immediately stop/pause scheduled automated outreach for that ticket.
3. Change status to REPLIED (or HOT_LEAD when intent is strong).
4. Create a HUMAN_HANDOVER event + notify the assigned user immediately.
5. Generate a handover dossier (message, history, previous outreach,
   intent/sentiment, suggested next action, exact handover timestamp).

The AI/system must NOT continue automated follow-ups after a qualifying
reply unless explicitly authorized — the dossier records the pause.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation, ConversationMessage
from app.models.enums import IntentLevel, NotificationType, TicketStatus
from app.models.ticket import Ticket, TicketStatus as TicketStatusRow
from app.services.audit_service import audit
from app.services.notification_service import notify_ticket_owner
from app.services.ticket_status_machine import assert_transition

logger = logging.getLogger("leadsynt.handover")

POSITIVE_SIGNALS = (
    "interested", "price", "quote", "cost", "budget", "proceed", "schedule",
    "meeting", "call", "details", "available", "how soon", "next steps",
)
NEGATIVE_SIGNALS = (
    "not interested", "no thank", "stop emailing", "unsubscribe", "remove me",
    "do not contact", "opt out",
)


def _classify(text: str) -> tuple[str, float]:
    low = (text or "").lower()
    pos = sum(1 for s in POSITIVE_SIGNALS if s in low)
    neg = sum(1 for s in NEGATIVE_SIGNALS if s in low)
    if neg > 0 and neg >= pos:
        return "negative", round(min(0.95, 0.5 + 0.15 * neg), 2)
    if pos > 0:
        return "positive", round(min(0.95, 0.5 + 0.15 * pos), 2)
    return "neutral", 0.5


def _suggested_action(sentiment: str, ticket: Ticket) -> str:
    if sentiment == "negative":
        return "Do not follow up automatically; add contact to suppression review queue."
    if sentiment == "positive":
        return (
            "Reply personally within the working day; propose a short call/meeting "
            "and confirm budget + timeline details."
        )
    return "Reply personally to clarify intent, budget and timeline before any automation resumes."


def _pause_automation(db: Session, ticket: Ticket) -> None:
    """Stop scheduled automated outreach for this ticket.

    The outreach scheduler (later phase) consults the ticket status and this
    audit event: no follow-ups while status is REPLIED/HOT_LEAD/AWAITING_HUMAN
    or a handover event exists without explicit re-authorization.
    """
    audit(
        db,
        action="outreach.automation_paused",
        actor_type="system",
        resource_type="ticket",
        resource_id=ticket.id,
        meta={"reason": "qualifying_reply_received"},
    )


def handle_reply(
    db: Session,
    *,
    ticket: Ticket,
    incoming_message: str,
    sender: str | None = None,
    contact_id: str | None = None,
    channel: str = "email",
    source: str = "webhook",
) -> dict:
    now = datetime.now(timezone.utc)

    # 1. Record the exact incoming message in the ticket's conversation.
    conv = db.execute(
        select(Conversation).where(Conversation.ticket_id == ticket.id)
    ).scalars().first()
    if conv is None:
        conv = Conversation(ticket_id=ticket.id, contact_id=contact_id, channel=channel)
        db.add(conv)
        db.flush()
    db.add(
        ConversationMessage(
            conversation_id=conv.id,
            direction="incoming",
            sender=sender,
            content=incoming_message,
            sent_at=now,
            metadata_={"source": source},
        )
    )
    conv.last_message_at = now

    # 2. Pause automated outreach immediately.
    _pause_automation(db, ticket)

    # 3. Classify intent/sentiment (deterministic, explainable).
    sentiment, sentiment_confidence = _classify(incoming_message)
    status_row = db.get(TicketStatusRow, ticket.status_id)
    current = TicketStatus(status_row.code) if status_row else None

    # Already in the reply/handover zone: no transition, still safe to re-handover.
    if current in (TicketStatus.REPLIED, TicketStatus.HOT_LEAD, TicketStatus.AWAITING_HUMAN):
        target = current
    else:
        target = TicketStatus.REPLIED
        if sentiment == "positive" and current is TicketStatus.OUTREACH_ACTIVE:
            target = TicketStatus.HOT_LEAD
        if current is not None and current is not target:
            assert_transition(current, target)
            target_row = db.execute(
                select(TicketStatusRow).where(TicketStatusRow.code == target.value)
            ).scalar_one()
            ticket.status_id = target_row.id
            ticket.status = target_row  # keep the relationship cache in sync

    ticket.last_activity_at = now

    # 4. Handover dossier + event + immediate notification.
    history = [
        {
            "direction": m.direction,
            "sender": m.sender,
            "content": m.content,
            "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        }
        for m in conv.messages
    ]
    dossier = {
        "incoming_message": incoming_message,
        "sender": sender,
        "channel": channel,
        "conversation_history": history,
        "previous_outreach_messages": sum(1 for m in history if m["direction"] == "outgoing"),
        "intent_classification": sentiment,
        "sentiment_confidence": sentiment_confidence,
        "ticket_intent_level": (ticket.intent_level.value
                                if hasattr(ticket.intent_level, "value")
                                else ticket.intent_level),
        "suggested_next_action": _suggested_action(sentiment, ticket),
        "automation_paused": True,
        "handover_timestamp": now.isoformat(),
    }
    audit(
        db,
        action="handover.created",
        actor_type="system",
        resource_type="ticket",
        resource_id=ticket.id,
        after=dossier,
        meta={"source": source},
    )
    notify_ticket_owner(
        db,
        ticket_id=ticket.id,
        owner_id=ticket.owner_id,
        type=NotificationType.HANDOVER,
        title=f"Prospect replied — handover: {ticket.reference}",
        body=f"Sentiment: {sentiment}. Suggested: {_suggested_action(sentiment, ticket)}",
    )
    logger.info("handover created for ticket %s", ticket.id, extra={"request_id": None})
    return dossier
