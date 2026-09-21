"""Outreach engine service (Phase B).

The send-time gatechain is the compliance heart of outreach. Every delivery
re-checks, live:

1. suppression (mandatory — DO-NOT-CONTACT, opt-out)
2. consent (withdrawn purposes block)
3. reply-pause / handover (no follow-ups after a qualifying reply unless a
   human explicitly authorized them)
4. per-contact daily cap
5. quiet hours

Then, and only then, the configured channel adapter performs the delivery.
Every decision is audited (``outreach.created``, ``outreach.sent``,
``outreach.queued``, ``outreach.failed``, ``outreach.blocked:<reason>``) and
published as an event, so everything the system did is reconstructable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.configuration import get_setting
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.company import Company, TicketCompany
from app.models.contact import Contact, TicketContact
from app.models.conversation import Conversation, ConversationMessage
from app.models.enums import TicketStatus
from app.models.ops import ConsentRecord
from app.models.outreach import (
    OutreachFollowUpAuthorization,
    OutreachMessage,
    OutreachTemplate,
)
from app.models.ticket import Ticket, TicketStatus as TicketStatusRow
from app.outreach.templates import (
    get_template,
    render_template,
)
from app.queues.events import (
    EVENT_OUTREACH_SENT,
    EVENT_OUTREACH_STARTED,
    EventBus,
)
from app.services.audit_service import audit
from app.services.suppression_service import check_outreach_allowed

logger = logging.getLogger("leadsynt.outreach")

REPLY_ZONE = {
    TicketStatus.REPLIED,
    TicketStatus.HOT_LEAD,
    TicketStatus.AWAITING_HUMAN,
}

# terminal states: once reached, a message is never re-sent
TERMINAL_STATES = {"SENT", "FAILED", "BLOCKED", "CANCELLED"}
SENDABLE_STATES = {"DRAFT", "SCHEDULED"}

CONSENT_PURPOSE_OUTREACH = "outreach"


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------


def _primary_contact(db: Session, ticket_id: str) -> Contact | None:
    tc = db.execute(
        select(TicketContact).where(TicketContact.ticket_id == ticket_id)
    ).scalars().first()
    if tc is None:
        return None
    return db.get(Contact, tc.contact_id)


def _company_for(db: Session, ticket_id: str) -> Company | None:
    tc = db.execute(
        select(TicketCompany).where(TicketCompany.ticket_id == ticket_id)
    ).scalars().first()
    if tc is None:
        return None
    return db.get(Company, tc.company_id)


def _status_code(db: Session, ticket: Ticket) -> TicketStatus | None:
    row = db.get(TicketStatusRow, ticket.status_id)
    if row is None:
        return None
    try:
        return TicketStatus(row.code)
    except ValueError:
        return None


def _in_reply_zone(db: Session, ticket: Ticket) -> bool:
    return _status_code(db, ticket) in REPLY_ZONE


def _consent_withdrawn(db: Session, contact: Contact | None) -> bool:
    if contact is None:
        return False
    row = db.execute(
        select(ConsentRecord.id).where(
            ConsentRecord.contact_id == contact.id,
            ConsentRecord.purpose == CONSENT_PURPOSE_OUTREACH,
            ConsentRecord.status == "WITHDRAWN",
        ).limit(1)
    ).first()
    return row is not None


def _daily_sent_count(db: Session, contact_id: str) -> int:
    """Messages SENT or QUEUED today for this contact (attempts count toward
    the per-contact cap regardless of transport)."""
    start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    row = db.execute(
        select(OutreachMessage.id)
        .where(
            OutreachMessage.contact_id == contact_id,
            OutreachMessage.status.in_(["SENT", "QUEUED"]),
            OutreachMessage.created_at >= start,
        )
        .limit(1000)
    ).scalars().all()
    return len(row)


def _is_quiet_hours(cfg: dict[str, Any], at: datetime) -> bool:
    """True when ``at`` (UTC) falls inside the configured quiet window
    HH:MM..HH:MM. Day-spanning windows (end < start) wrap past midnight.
    Quiet hours are opt-in via ``quiet_hours_enabled`` (default off)."""
    if cfg.get("quiet_hours_enabled") is not True:
        return False
    qh = cfg.get("quiet_hours") or {}
    start_s, end_s = str(qh.get("start", "")), str(qh.get("end", ""))
    if ":" not in start_s or ":" not in end_s:
        return False

    def _minutes(value: str) -> int:
        hh, mm = value.split(":")
        return int(hh) * 60 + int(mm)

    clock = at.hour * 60 + at.minute
    start, end = _minutes(start_s), _minutes(end_s)
    if start == end:
        return False
    if end > start:
        return start <= clock < end
    return clock >= start or clock < end


# ---------------------------------------------------------------------------
# Message lifecycle
# ---------------------------------------------------------------------------


def create_message(
    db: Session,
    *,
    ticket_id: str,
    contact_id: str | None = None,
    template_id: str | None = None,
    template_name: str | None = None,
    channel: str = "email",
    subject: str | None = None,
    body: str | None = None,
    sequence: int = 1,
    scheduled_for: datetime | None = None,
    actor_id: str | None = None,
    actor_type: str = "user",
) -> OutreachMessage:
    """Create an outreach message. Renders the template (or an explicit
    subject+body); SCHEDULED when ``scheduled_for`` is set, DRAFT otherwise.
    The drafted *body is a snapshot* — send-time re-checks the compliance
    gates but does not re-render, so provenance is exact."""
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise NotFoundError("Ticket not found", details={"ticket_id": ticket_id})

    target_contact_id = contact_id
    if target_contact_id is None:
        primary = _primary_contact(db, ticket_id)
        target_contact_id = primary.id if primary else None
    if target_contact_id is None:
        raise BadRequestError(
            "Ticket has no contact; supply contact_id",
            details={"ticket_id": ticket_id},
        )
    if db.get(Contact, target_contact_id) is None:
        raise NotFoundError("Contact not found", details={"contact_id": target_contact_id})

    channel = (channel or "email").lower()
    sequence = max(1, int(sequence or 1))

    template: OutreachTemplate | None = None
    if template_id:
        template = db.get(OutreachTemplate, template_id)
        if template is None:
            raise NotFoundError("Template not found", details={"template_id": template_id})
    elif template_name:
        template = get_template(db, template_name)
        if template is None:
            raise NotFoundError("Template not found", details={"template_name": template_name})

    contact = db.get(Contact, target_contact_id)
    company = _company_for(db, ticket_id)
    meta: dict[str, Any] = {}
    if template is not None:
        subject, body, meta = render_template(
            template, contact=contact, company=company, ticket=ticket
        )
    elif subject is None or body is None:
        raise BadRequestError("subject and body are required when no template is given")
    else:
        # Operator-authored body still gets the compliance opt-out footer.
        from app.outreach.templates import FOOTER

        if FOOTER not in body:
            body = (body or "") + FOOTER
        meta = {"template": None, "footer_appended": True, "unresolved_vars": []}

    msg = OutreachMessage(
        ticket_id=ticket_id,
        contact_id=target_contact_id,
        template_id=template.id if template else None,
        channel=channel,
        sequence=sequence,
        subject=subject.strip(),
        body=body.strip(),
        status="SCHEDULED" if scheduled_for else "DRAFT",
        scheduled_for=scheduled_for,
        sent_by=actor_id,
        meta=meta,
    )
    db.add(msg)
    db.flush()
    audit(
        db,
        action="outreach.created",
        actor_id=actor_id,
        actor_type=actor_type,
        resource_type="outreach_message",
        resource_id=msg.id,
        after={
            "ticket_id": ticket_id,
            "contact_id": target_contact_id,
            "channel": channel,
            "sequence": sequence,
            "status": msg.status,
            "template": template.name if template else None,
            "subject": msg.subject,
        },
        meta=meta,
    )
    if msg.status == "SCHEDULED":
        EventBus.publish(EVENT_OUTREACH_STARTED, {
            "message_id": msg.id, "ticket_id": ticket_id, "channel": channel,
        })
    db.flush()
    return msg


def _block(
    db: Session,
    message: OutreachMessage,
    reason: str,
    detail: str,
    *,
    actor_id: str | None,
    actor_type: str,
) -> dict[str, Any]:
    prev = message.status
    message.status = "BLOCKED"
    message.error = f"{reason}: {detail}"
    meta = dict(message.meta or {})
    meta["block_reason"] = reason
    meta["previous_status"] = prev
    message.meta = meta
    audit(
        db,
        action=f"outreach.blocked:{reason}",
        actor_id=actor_id,
        actor_type=actor_type,
        resource_type="outreach_message",
        resource_id=message.id,
        before={"status": prev},
        after={"status": "BLOCKED", "reason": reason, "detail": detail},
    )
    db.flush()
    return {
        "message_id": message.id, "status": "BLOCKED", "delivered": False,
        "block_reason": reason, "why": detail,
    }


def _fail(
    db: Session,
    message: OutreachMessage,
    error: str,
    *,
    actor_id: str | None,
    actor_type: str,
) -> dict[str, Any]:
    prev = message.status
    message.status = "FAILED"
    message.error = error
    audit(
        db,
        action="outreach.failed",
        actor_id=actor_id,
        actor_type=actor_type,
        resource_type="outreach_message",
        resource_id=message.id,
        before={"status": prev},
        after={"status": "FAILED", "error": error},
    )
    db.flush()
    return {"message_id": message.id, "status": "FAILED", "delivered": False, "error": error}


def _record_outgoing(db: Session, message: OutreachMessage, contact: Contact | None) -> None:
    conv = db.execute(
        select(Conversation).where(Conversation.ticket_id == message.ticket_id)
    ).scalars().first()
    if conv is None:
        conv = Conversation(ticket_id=message.ticket_id, contact_id=message.contact_id, channel=message.channel)
        db.add(conv)
        db.flush()
    db.add(
        ConversationMessage(
            conversation_id=conv.id,
            direction="outgoing",
            sender=contact.work_email if contact else None,
            content=message.body,
            sent_at=message.sent_at or datetime.now(timezone.utc),
            metadata_={
                "channel": message.channel,
                "transport": message.transport,
                "provider_ref": message.provider_ref,
                "sequence": message.sequence,
                "outreach_message_id": message.id,
            },
        )
    )
    conv.last_message_at = datetime.now(timezone.utc)
    db.flush()


def _followup_authorized(db: Session, message: OutreachMessage) -> bool:
    """In the reply/handover zone, a follow-up may only be sent when a human
    explicitly authorized it and the message sequence is within the cap."""
    row = db.execute(
        select(OutreachFollowUpAuthorization).where(
            OutreachFollowUpAuthorization.ticket_id == message.ticket_id
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    if row.max_follow_ups <= 0:
        return False
    return message.sequence <= row.max_follow_ups


def deliver_message(
    db: Session,
    *,
    message: OutreachMessage,
    actor_id: str | None = None,
    actor_type: str = "user",
) -> dict[str, Any]:
    """Drive one message through the send-time gatechain, then the channel
    adapter. Idempotent for already-terminal messages, audited throughout."""
    if message.status in TERMINAL_STATES:
        return {
            "message_id": message.id, "status": message.status,
            "delivered": False, "note": f"already {message.status.lower()}",
        }
    if message.status not in SENDABLE_STATES:
        raise BadRequestError(
            f"Message state {message.status} is not sendable",
            details={"message_id": message.id, "state": message.status},
        )

    ticket = db.get(Ticket, message.ticket_id)
    contact = db.get(Contact, message.contact_id) if message.contact_id else None
    if ticket is None:
        return _fail(db, message, "ticket no longer exists", actor_id=actor_id, actor_type=actor_type)

    # 1. suppression — the mandatory live re-check
    if contact is not None:
        # resolve suppression directly (raises on block -> recorded as BLOCKED)
        from app.core.exceptions import SuppressedContactError

        try:
            check_outreach_allowed(db, contact)
        except SuppressedContactError as exc:
            return _block(db, message, "suppression", str(exc), actor_id=actor_id, actor_type=actor_type)
    else:
        # no contact row: block when the ticket-level record is suppressed
        from app.models.ops import SuppressionRecord

        rec = db.execute(
            select(SuppressionRecord.id).where(
                SuppressionRecord.scope == "contact",
                SuppressionRecord.value == message.contact_id,
                SuppressionRecord.expires_at.is_(None),
            ).limit(1)
        ).first()
        if rec is not None:
            return _block(db, message, "suppression", "contact is suppressed (DO-NOT-CONTACT)", actor_id=actor_id, actor_type=actor_type)

    # 2. consent — withdrawn purpose blocks
    if _consent_withdrawn(db, contact):
        return _block(db, message, "consent", "outreach consent was withdrawn", actor_id=actor_id, actor_type=actor_type)

    # 3. reply-pause / handover hard rule
    if _in_reply_zone(db, ticket) and not _followup_authorized(db, message):
        return _block(
            db, message, "reply_pause",
            "ticket is in the reply/handover zone and follow-ups are not authorized",
            actor_id=actor_id, actor_type=actor_type,
        )

    # 4. per-contact daily cap
    cfg: dict[str, Any] = get_setting(db, "outreach", {}) or {}
    cap = int(cfg.get("max_daily_per_contact", 0) or 0)
    if cap > 0 and contact is not None and _daily_sent_count(db, contact.id) >= cap:
        return _block(
            db, message, "daily_cap",
            f"daily cap of {cap} message(s) per contact reached",
            actor_id=actor_id, actor_type=actor_type,
        )

    # 5. quiet hours
    if _is_quiet_hours(cfg, datetime.now(timezone.utc)):
        return _block(db, message, "quiet_hours", "send attempted during configured quiet hours", actor_id=actor_id, actor_type=actor_type)

    # 6. channel adapter
    from app.outreach.base import get_channel_adapter

    adapter = get_channel_adapter(db, message.channel)
    result = adapter.send(message=message, contact=contact, ticket=ticket)

    if result.error:
        return _fail(db, message, result.error, actor_id=actor_id, actor_type=actor_type)

    if result.delivered:
        now = datetime.now(timezone.utc)
        prev = message.status
        message.status = "SENT"
        message.sent_at = now
        message.provider_ref = result.provider_ref
        message.transport = result.transport
        _record_outgoing(db, message, contact)
        audit(
            db,
            action="outreach.sent",
            actor_id=actor_id,
            actor_type=actor_type,
            resource_type="outreach_message",
            resource_id=message.id,
            before={"status": prev},
            after={
                "status": "SENT", "channel": message.channel,
                "transport": result.transport, "provider_ref": result.provider_ref,
                "sequence": message.sequence,
            },
        )
        EventBus.publish(EVENT_OUTREACH_SENT, {
            "message_id": message.id, "ticket_id": message.ticket_id,
            "channel": message.channel, "provider_ref": result.provider_ref,
        })
        db.flush()
        return {
            "message_id": message.id, "status": "SENT", "delivered": True,
            "provider_ref": result.provider_ref, "transport": result.transport,
        }

    if result.queued:
        prev = message.status
        message.status = "QUEUED"
        message.transport = result.transport or "log"
        audit(
            db,
            action="outreach.queued",
            actor_id=actor_id,
            actor_type=actor_type,
            resource_type="outreach_message",
            resource_id=message.id,
            before={"status": prev},
            after={"status": "QUEUED", "transport": message.transport,
                   "note": result.note},
        )
        db.flush()
        return {
            "message_id": message.id, "status": "QUEUED", "delivered": False,
            "note": result.note or "queued to outbound log",
        }

    # adapter returned nothing actionable
    return _fail(db, message, "adapter returned no result", actor_id=actor_id, actor_type=actor_type)


def run_due(db: Session, *, actor_id: str | None = None, actor_type: str = "system") -> dict[str, Any]:
    """Deliver every SCHEDULED message currently due (scheduled_for <= now or
    unscheduled). Called by the API and the Celery ``outreach.send_due`` task;
    every gate (suppression/consent/reply-pause/cap/quiet-hours) still applies
    per message at send time."""
    now = datetime.now(timezone.utc)
    due = db.execute(
        select(OutreachMessage)
        .where(
            OutreachMessage.status == "SCHEDULED",
            or_(
                OutreachMessage.scheduled_for.is_(None),
                OutreachMessage.scheduled_for <= now,
            ),
        )
        .order_by(
            OutreachMessage.scheduled_for.is_(None).asc(),
            OutreachMessage.scheduled_for.asc(),
        )
    ).scalars().all()

    summary: dict[str, Any] = {"attempted": 0, "sent": 0, "queued": 0, "failed": 0, "blocked": 0, "blocked_by": {}}
    for msg in due:
        outcome = deliver_message(db, message=msg, actor_id=actor_id, actor_type=actor_type)
        summary["attempted"] += 1
        summary[outcome["status"].lower()] = summary.get(outcome["status"].lower(), 0) + 1
        if outcome["status"] == "BLOCKED":
            reason = outcome.get("block_reason", "unknown")
            summary["blocked_by"][reason] = summary["blocked_by"].get(reason, 0) + 1
    db.flush()
    return summary


def cancel_message(db: Session, *, message: OutreachMessage, actor_id: str | None = None) -> dict[str, Any]:
    """Cancel a DRAFT/SCHEDULED message (audited). Terminal states are left
    untouched."""
    prev = message.status
    if prev in TERMINAL_STATES:
        return {"message_id": message.id, "status": message.status, "note": f"already {prev.lower()}"}
    message.status = "CANCELLED"
    if not message.error:
        message.error = "cancelled by operator"
    audit(
        db,
        action="outreach.cancelled",
        actor_id=actor_id,
        actor_type="user" if actor_id else "system",
        resource_type="outreach_message",
        resource_id=message.id,
        before={"status": prev},
        after={"status": "CANCELLED"},
    )
    db.flush()
    return {"message_id": message.id, "status": "CANCELLED", "delivered": False}


def authorize_follow_ups(
    db: Session,
    *,
    ticket_id: str,
    authorized_by: str,
    max_follow_ups: int = 2,
    notes: str | None = None,
) -> OutreachFollowUpAuthorization:
    """Explicit human authorization to send queued follow-ups after a
    reply/handover pause. Fully audited; does NOT re-enable anything else."""
    if db.get(Ticket, ticket_id) is None:
        raise NotFoundError("Ticket not found", details={"ticket_id": ticket_id})
    now = datetime.now(timezone.utc)
    row = db.execute(
        select(OutreachFollowUpAuthorization).where(
            OutreachFollowUpAuthorization.ticket_id == ticket_id
        )
    ).scalar_one_or_none()
    if row is None:
        row = OutreachFollowUpAuthorization(
            ticket_id=ticket_id, authorized_by=authorized_by,
            authorized_at=now, max_follow_ups=max(0, int(max_follow_ups or 0)),
            notes=notes,
        )
        db.add(row)
    else:
        row.authorized_by = authorized_by
        row.authorized_at = now
        row.max_follow_ups = max(0, int(max_follow_ups or 0))
        row.notes = notes
    db.flush()
    audit(
        db,
        action="outreach.followup.authorized",
        actor_id=authorized_by,
        actor_type="user",
        resource_type="ticket",
        resource_id=ticket_id,
        after={
            "authorized_at": now.isoformat(),
            "max_follow_ups": row.max_follow_ups,
            "notes": notes,
        },
    )
    db.flush()
    return row