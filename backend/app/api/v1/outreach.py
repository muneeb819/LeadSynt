"""Outreach API (Phase B): templates, messages, follow-up rules +
authorizations, and the send-time runner.

Sending is always gated by the live compliance gatechain in the outreach
service — an endpoint can never bypass suppression/consent/reply-pause.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import NotFoundError
from app.models.outreach import (
    FollowUpRule,
    OutreachFollowUpAuthorization,
    OutreachMessage,
    OutreachTemplate,
)
from app.schemas.common import Envelope
from app.schemas.outreach import (
    FollowUpAuthorizeIn,
    FollowUpRuleCreate,
    OutreachMessageCreate,
    OutreachTemplateCreate,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _template_out(t: OutreachTemplate) -> dict:
    return {
        "id": t.id, "name": t.name, "channel": t.channel,
        "subject": t.subject, "body": t.body, "description": t.description,
        "is_active": t.is_active, "created_by": t.created_by,
    }


def _message_out(m: OutreachMessage) -> dict:
    return {
        "id": m.id, "ticket_id": m.ticket_id, "contact_id": m.contact_id,
        "template_id": m.template_id, "channel": m.channel, "sequence": m.sequence,
        "subject": m.subject, "body": m.body, "status": m.status,
        "scheduled_for": m.scheduled_for.isoformat() if m.scheduled_for else None,
        "sent_at": m.sent_at.isoformat() if m.sent_at else None,
        "provider_ref": m.provider_ref, "transport": m.transport, "error": m.error,
        "sent_by": m.sent_by, "meta": m.meta,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _rule_out(r: FollowUpRule) -> dict:
    return {
        "id": r.id, "name": r.name, "channel": r.channel, "sequence": r.sequence,
        "delay_hours": r.delay_hours, "max_follow_ups": r.max_follow_ups,
        "requires_human_authorization": r.requires_human_authorization,
        "is_active": r.is_active, "description": r.description,
    }


def _auth_out(a: OutreachFollowUpAuthorization) -> dict:
    return {
        "id": a.id, "ticket_id": a.ticket_id, "authorized_by": a.authorized_by,
        "authorized_at": a.authorized_at.isoformat() if a.authorized_at else None,
        "max_follow_ups": a.max_follow_ups, "notes": a.notes,
    }


# ---------------------------------------------------------------------------
# Templates (library)
# ---------------------------------------------------------------------------

@router.get("/templates", response_model=Envelope)
def list_templates(
    active_only: bool = Query(False),
    user=Depends(require_permission("outreach:read")),
    db: Session = Depends(get_db),
):
    q = select(OutreachTemplate).order_by(OutreachTemplate.name)
    if active_only:
        q = q.where(OutreachTemplate.is_active.is_(True))
    rows = db.execute(q).scalars().all()
    return Envelope(data=[_template_out(t) for t in rows])


@router.post("/templates", response_model=Envelope, status_code=201)
def create_template(
    body: OutreachTemplateCreate,
    user=Depends(require_permission("outreach:manage")),
    db: Session = Depends(get_db),
):
    from app.outreach.templates import VAR_RE

    # report placeholders that the renderer would not resolve at send time
    declared = set(VAR_RE.findall(body.subject)) | set(VAR_RE.findall(body.body))
    known = {"first_name", "full_name", "company_name", "reference", "sender_name"}
    t = OutreachTemplate(
        name=body.name, channel=body.channel.lower(), subject=body.subject,
        body=body.body, description=body.description, is_active=body.is_active,
        created_by=user.id,
    )
    db.add(t)
    db.flush()
    from app.services.audit_service import audit

    audit(db, action="outreach.template.created", actor_id=user.id, actor_type="user",
          resource_type="outreach_template", resource_id=t.id,
          after={"name": t.name, "channel": t.channel, "unknown_placeholders": sorted(declared - known)})
    db.commit()
    return Envelope(data=_template_out(t))


# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

@router.get("/messages", response_model=Envelope)
def list_messages(
    ticket_id: str | None = None,
    contact_id: str | None = None,
    status: str | None = None,
    channel: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    user=Depends(require_permission("outreach:read")),
    db: Session = Depends(get_db),
):
    q = select(OutreachMessage).order_by(OutreachMessage.created_at.desc())
    if ticket_id:
        q = q.where(OutreachMessage.ticket_id == ticket_id)
    if contact_id:
        q = q.where(OutreachMessage.contact_id == contact_id)
    if status:
        q = q.where(OutreachMessage.status == status.upper())
    if channel:
        q = q.where(OutreachMessage.channel == channel.lower())
    rows = db.execute(q.limit(limit)).scalars().all()
    return Envelope(data=[_message_out(m) for m in rows])


@router.post("/messages", response_model=Envelope, status_code=201)
def create_message(
    body: OutreachMessageCreate,
    user=Depends(require_permission("outreach:send")),
    db: Session = Depends(get_db),
):
    from app.outreach.service import create_message as service_create

    msg = service_create(
        db,
        ticket_id=body.ticket_id,
        contact_id=body.contact_id,
        template_id=body.template_id,
        template_name=body.template_name,
        channel=body.channel,
        subject=body.subject,
        body=body.body,
        sequence=body.sequence,
        scheduled_for=body.scheduled_for,
        actor_id=user.id,
        actor_type="user",
    )
    db.commit()
    return Envelope(data=_message_out(msg))


@router.post("/messages/run-due", response_model=Envelope)
def run_due(
    user=Depends(require_permission("outreach:send")),
    db: Session = Depends(get_db),
):
    """Deliver all due SCHEDULED messages through the full compliance
    gatechain (suppression/consent/reply-pause/daily-cap/quiet-hours)."""
    from app.outreach.service import run_due as service_run_due

    summary = service_run_due(db, actor_id=user.id, actor_type="user")
    db.commit()
    return Envelope(data=summary)


@router.get("/messages/{message_id}", response_model=Envelope)
def get_message(
    message_id: str,
    user=Depends(require_permission("outreach:read")),
    db: Session = Depends(get_db),
):
    m = db.get(OutreachMessage, message_id)
    if m is None:
        raise NotFoundError("Message not found", details={"message_id": message_id})
    return Envelope(data=_message_out(m))


@router.post("/messages/{message_id}/send", response_model=Envelope)
def send_message(
    message_id: str,
    user=Depends(require_permission("outreach:send")),
    db: Session = Depends(get_db),
):
    """Deliver one message now, through the full send-time gatechain."""
    from app.outreach.service import deliver_message

    m = db.get(OutreachMessage, message_id)
    if m is None:
        raise NotFoundError("Message not found", details={"message_id": message_id})
    outcome = deliver_message(db, message=m, actor_id=user.id, actor_type="user")
    db.commit()
    return Envelope(data=outcome)


@router.post("/messages/{message_id}/cancel", response_model=Envelope)
def cancel_message(
    message_id: str,
    user=Depends(require_permission("outreach:send")),
    db: Session = Depends(get_db),
):
    from app.outreach.service import cancel_message as service_cancel

    m = db.get(OutreachMessage, message_id)
    if m is None:
        raise NotFoundError("Message not found", details={"message_id": message_id})
    outcome = service_cancel(db, message=m, actor_id=user.id)
    db.commit()
    return Envelope(data=outcome)


# ---------------------------------------------------------------------------
# Follow-up rules + explicit human authorization
# ---------------------------------------------------------------------------

@router.get("/follow-ups", response_model=Envelope)
def list_follow_ups(
    user=Depends(require_permission("outreach:read")),
    db: Session = Depends(get_db),
):
    rows = db.execute(select(FollowUpRule).order_by(FollowUpRule.channel, FollowUpRule.sequence)).scalars().all()
    return Envelope(data=[_rule_out(r) for r in rows])


@router.post("/follow-ups", response_model=Envelope, status_code=201)
def create_follow_up_rule(
    body: FollowUpRuleCreate,
    user=Depends(require_permission("outreach:manage")),
    db: Session = Depends(get_db),
):
    from app.core.exceptions import ConflictError

    existing = db.execute(
        select(FollowUpRule).where(
            FollowUpRule.channel == body.channel.lower(),
            FollowUpRule.sequence == body.sequence,
        )
    ).scalars().first()
    if existing is not None:
        raise ConflictError("A rule already exists for this channel/sequence",
                            details={"channel": body.channel, "sequence": body.sequence})
    r = FollowUpRule(
        name=body.name, channel=body.channel.lower(), sequence=body.sequence,
        delay_hours=body.delay_hours, max_follow_ups=body.max_follow_ups,
        requires_human_authorization=body.requires_human_authorization,
        is_active=body.is_active, description=body.description,
    )
    db.add(r)
    db.flush()
    from app.services.audit_service import audit

    audit(db, action="outreach.followup.rule.created", actor_id=user.id, actor_type="user",
          resource_type="follow_up_rule", resource_id=r.id,
          after={"name": r.name, "channel": r.channel, "sequence": r.sequence,
                 "delay_hours": r.delay_hours})
    db.commit()
    return Envelope(data=_rule_out(r))


@router.get("/follow-ups/authorizations", response_model=Envelope)
def list_authorizations(
    ticket_id: str | None = None,
    user=Depends(require_permission("outreach:read")),
    db: Session = Depends(get_db),
):
    q = select(OutreachFollowUpAuthorization).order_by(
        OutreachFollowUpAuthorization.authorized_at.desc()
    )
    if ticket_id:
        q = q.where(OutreachFollowUpAuthorization.ticket_id == ticket_id)
    rows = db.execute(q).scalars().all()
    return Envelope(data=[_auth_out(a) for a in rows])


@router.post("/follow-ups/authorize", response_model=Envelope)
def authorize_follow_ups(
    body: FollowUpAuthorizeIn,
    user=Depends(require_permission("outreach:send")),
    db: Session = Depends(get_db),
):
    """Explicit human authorization: allow queued follow-ups on a ticket that
    is paused by the reply-handover rule. Fully audited."""
    from app.outreach.service import authorize_follow_ups as service_authorize

    row = service_authorize(
        db,
        ticket_id=body.ticket_id,
        authorized_by=user.id,
        max_follow_ups=body.max_follow_ups,
        notes=body.notes,
    )
    db.commit()
    return Envelope(data=_auth_out(row))