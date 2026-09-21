"""Inbound reply webhook — the entry point of the CRITICAL handover rule.

Flow: signature verification (HMAC-SHA256, timestamp-bounded) -> record
webhook event -> route the reply (Phase B: resolve the ticket by ticket_id /
outbound thread reference / sender identity, validate the channel, honor
explicit opt-outs as audited suppressions) -> handover service (pause
automation, record verbatim message, transition to REPLIED/HOT_LEAD,
dossier, notify owner).

Invalid signatures are rejected with 401 AND recorded (signature_verified
=False, status=FAILED) so abuse attempts are visible. Unresolvable replies
(or unsupported channels) are recorded as FAILED with the reason.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.exceptions import AppError, BadRequestError, UnauthorizedError
from app.models.ops import WebhookEvent
from app.outreach.reply_router import route_reply
from app.security import verify_signature
from app.services.audit_service import audit

logger = logging.getLogger("leadsynt.webhooks")

router = APIRouter()


@router.post("/reply", status_code=200)
async def reply_webhook(request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    body = await request.body()
    signature = request.headers.get("X-LeadSynt-Signature")
    timestamp = request.headers.get("X-LeadSynt-Timestamp")
    source = request.headers.get("X-LeadSynt-Source", "unknown")

    signed = verify_signature(s.webhook_shared_secret, body, signature, timestamp, s.webhook_signature_tolerance_seconds)

    data = {}
    if body:
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

    event = WebhookEvent(
        source=source,
        event_type="prospect.replied",
        payload=data,
        signature_verified=signed,
        status="RECEIVED",
        received_at=datetime.now(timezone.utc),
    )
    db.add(event)

    if not signed:
        event.status = "FAILED"
        event.error = "signature verification failed"
        audit(db, action="webhook.rejected", actor_type="webhook",
              resource_type="webhook_event", resource_id=event.id,
              meta={"source": source, "reason": "bad_signature"})
        db.commit()
        raise UnauthorizedError("Webhook signature verification failed")

    message = data.get("message")
    if not message:
        event.status = "FAILED"
        event.error = "missing message"
        db.commit()
        raise BadRequestError("Webhook payload requires a message")

    try:
        routed = route_reply(
            db,
            message=str(message),
            sender=data.get("sender"),
            channel=data.get("channel", "email"),
            thread_id=data.get("thread_id") or data.get("message_id"),
            message_id=data.get("message_id"),
            contact_id=data.get("contact_id"),
            ticket_id=data.get("ticket_id"),
            source=source,
        )
    except AppError as exc:
        event.status = "FAILED"
        event.error = exc.message
        db.commit()
        raise

    event.status = "PROCESSED"
    event.processed_at = datetime.now(timezone.utc)
    from app.queues.events import EVENT_HANDOVER_CREATED, EventBus

    EventBus.publish(EVENT_HANDOVER_CREATED, {"ticket_id": routed["ticket_id"]})
    db.commit()
    return {
        "status": "processed",
        "ticket_id": routed["ticket_id"],
        "handover": routed.get("suggested_next_action"),
    }