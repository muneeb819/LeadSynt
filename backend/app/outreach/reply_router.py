"""Reply routing hardening (Phase B).

Replies arrive from multiple platforms. This router:

- resolves WHICH ticket a reply belongs to (by ``ticket_id``, an external
  thread reference recorded on the outbound message, sender identity, or
  contact id),
- validates the channel is supported (multi-platform surface),
- honors explicit opt-outs IMMEDIATELY as suppression records (audited +
  owner notification), and
- then runs the unchanged critical handover flow.

The critical handover rule is never weakened here: pause automation, status
to REPLIED/HOT_LEAD, dossier, notify owner.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.contact import Contact, TicketContact
from app.models.enums import NotificationType
from app.models.outreach import OutreachMessage
from app.models.ticket import Ticket
from app.queues.events import EVENT_PROSPECT_REPLIED, EventBus
from app.services import handover_service
from app.services.audit_service import audit
from app.services.notification_service import notify_ticket_owner
from app.services.suppression_service import add_suppression

logger = logging.getLogger("leadsynt.outreach.reply")

# Extensible multi-platform surface: add a channel here + a normalizer later.
SUPPORTED_CHANNELS = {"email", "sms", "web"}

EXPLICIT_OPT_OUT_SIGNALS = (
    "unsubscribe",
    "stop emailing",
    "remove me",
    "take me off",
    "do not contact",
    "opt out",
    "no more emails",
    "don't email",
)


def _ticket_id_by_thread(db: Session, thread_id: str) -> str | None:
    """Match a provider thread reference back to the ticket that owns the
    outbound message (multi-platform: email Message-ID, SMS session id...)."""
    row = db.execute(
        select(OutreachMessage)
        .where(OutreachMessage.provider_ref == thread_id)
        .order_by(OutreachMessage.created_at.desc())
        .limit(1)
    ).scalars().first()
    return row.ticket_id if row is not None else None


def resolve_ticket(
    db: Session,
    *,
    ticket_id: str | None = None,
    thread_id: str | None = None,
    sender: str | None = None,
    contact_id: str | None = None,
) -> Ticket | None:
    """Return the ticket for this reply, or None. Resolution order: explicit
    ticket_id -> outbound thread reference -> sender email identity ->
    contact id."""
    if ticket_id:
        return db.get(Ticket, ticket_id)
    if thread_id:
        tid = _ticket_id_by_thread(db, thread_id)
        if tid:
            t = db.get(Ticket, tid)
            if t is not None:
                return t
    if sender and "@" in (sender or ""):
        c = db.execute(
            select(Contact).where(func.lower(Contact.work_email) == sender.lower())
        ).scalars().first()
        if c is not None:
            tc = db.execute(
                select(TicketContact).where(TicketContact.contact_id == c.id)
            ).scalars().first()
            if tc is not None:
                t = db.get(Ticket, tc.ticket_id)
                if t is not None:
                    return t
    if contact_id:
        tc = db.execute(
            select(TicketContact).where(TicketContact.contact_id == contact_id)
        ).scalars().first()
        if tc is not None:
            t = db.get(Ticket, tc.ticket_id)
            if t is not None:
                return t
    return None


def _is_opt_out(message: str) -> bool:
    low = (message or "").lower()
    return any(signal in low for signal in EXPLICIT_OPT_OUT_SIGNALS)


def _apply_opt_out(db: Session, *, ticket: Ticket, sender: str | None, contact_id: str | None, source: str) -> None:
    """Record an explicit opt-out as a suppression (audited + notified). The
    handover flow still runs afterwards so the owner sees the full reply."""
    contact = None
    if contact_id:
        contact = db.get(Contact, contact_id)
    if contact is None and sender and "@" in (sender or ""):
        contact = db.execute(
            select(Contact).where(func.lower(Contact.work_email) == sender.lower())
        ).scalars().first()

    value = sender or (contact.work_email if contact else None)
    scope = "email" if value and "@" in value else ("contact" if contact else "email")
    if not value and contact:
        value = contact.id
        scope = "contact"
    if not value:
        logger.info("opt-out reply without resolvable identity; suppression skipped", extra={"ticket_id": ticket.id})
        return

    rec = add_suppression(
        db,
        scope=scope,
        value=value,
        contact_id=contact.id if contact else None,
        reason="explicit opt-out in reply",
        source=source,
    )
    audit(
        db,
        action="outreach.opted_out",
        actor_type="webhook",
        resource_type="ticket",
        resource_id=ticket.id,
        after={"suppression_id": rec.id, "scope": scope, "value": value, "contact_id": contact.id if contact else None},
        meta={"source": source},
    )
    notify_ticket_owner(
        db,
        ticket_id=ticket.id,
        owner_id=ticket.owner_id,
        type=NotificationType.HANDOVER,
        title=f"Opt-out received — {ticket.reference}",
        body="The prospect asked to be removed from outreach; suppression was recorded.",
    )
    logger.info("opt-out suppression recorded for ticket %s", ticket.id)


def route_reply(
    db: Session,
    *,
    message: str,
    sender: str | None = None,
    channel: str = "email",
    thread_id: str | None = None,
    message_id: str | None = None,
    contact_id: str | None = None,
    ticket_id: str | None = None,
    source: str = "webhook",
) -> dict[str, Any]:
    """Resolve + validate + honor opt-out + run the critical handover flow.
    Returns the handover dossier enriched with ticket/channel context."""
    channel = (channel or "email").lower()
    if channel not in SUPPORTED_CHANNELS:
        audit(
            db,
            action="webhook.rejected:unsupported_channel",
            actor_type="webhook",
            resource_type="ticket",
            meta={"channel": channel, "source": source},
        )
        raise BadRequestError(
            f"Unsupported reply channel: {channel}",
            details={"channel": channel, "supported": sorted(SUPPORTED_CHANNELS)},
        )

    ticket = resolve_ticket(
        db, ticket_id=ticket_id, thread_id=thread_id,
        sender=sender, contact_id=contact_id,
    )
    if ticket is None:
        raise NotFoundError(
            "Could not resolve a ticket for this reply",
            details={"ticket_id": ticket_id, "thread_id": thread_id,
                     "sender": sender, "contact_id": contact_id},
        )

    if _is_opt_out(message):
        _apply_opt_out(db, ticket=ticket, sender=sender, contact_id=contact_id, source=source)

    dossier = handover_service.handle_reply(
        db,
        ticket=ticket,
        incoming_message=str(message),
        sender=sender,
        contact_id=contact_id,
        channel=channel,
        source=source,
    )
    EventBus.publish(EVENT_PROSPECT_REPLIED, {"ticket_id": ticket.id, "channel": channel})
    return {**dossier, "ticket_id": ticket.id, "channel": channel}