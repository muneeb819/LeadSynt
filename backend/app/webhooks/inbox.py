"""Inbound reply webhook — the entry point of the CRITICAL handover rule.

Flow: signature verification (HMAC-SHA256, timestamp-bounded) -> record
webhook event -> load ticket -> handover service (pause automation, record
verbatim message, transition to REPLIED/HOT_LEAD, dossier, notify owner).

Invalid signatures are rejected with 401 AND recorded (signature_verified
=False, status=FAILED) so abuse attempts are visible.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.exceptions import BadRequestError, NotFoundError, UnauthorizedError
from app.models.ops import WebhookEvent
from app.models.ticket import Ticket
from app.security import verify_signature
from app.services import handover_service
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
        import json

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

    ticket_id = data.get("ticket_id")
    message = data.get("message")
    if not ticket_id or not message:
        event.status = "FAILED"
        event.error = "missing ticket_id or message"
        db.commit()
        raise BadRequestError("Webhook payload requires ticket_id and message")

    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        event.status = "FAILED"
        event.error = f"unknown ticket {ticket_id}"
        db.commit()
        raise NotFoundError("Ticket not found", details={"ticket_id": ticket_id})

    dossier = handover_service.handle_reply(
        db,
        ticket=ticket,
        incoming_message=str(message),
        sender=data.get("sender"),
        contact_id=data.get("contact_id"),
        channel=data.get("channel", "email"),
        source=source,
    )

    event.status = "PROCESSED"
    event.processed_at = datetime.now(timezone.utc)
    from app.queues.events import EventBus, EVENT_PROSPECT_REPLIED, EVENT_HANDOVER_CREATED

    EventBus.publish(EVENT_PROSPECT_REPLIED, {"ticket_id": ticket.id})
    EventBus.publish(EVENT_HANDOVER_CREATED, {"ticket_id": ticket.id})
    db.commit()
    return {"status": "processed", "ticket_id": ticket.id, "handover": dossier["suggested_next_action"]}
