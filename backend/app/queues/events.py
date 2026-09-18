"""Event bus — the event-driven foundation.

Event names follow the spec (ticket.created, outreach.sent, prospect.replied,
handover.created, connector.started, ai.run.completed, qa.finding.created,
change.request.created, ...).

Transport:
- Redis pub/sub channel ``leadsynt:events`` when Redis is reachable
  (production/compose profile).
- In-process subscribers always (workers, SSE feeds, tests).

Events are a notification channel, not the system of record — business data
changes are committed first, then the event is published.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

logger = logging.getLogger("leadsynt.events")

EVENT_TICKET_CREATED = "ticket.created"
EVENT_TICKET_UPDATED = "ticket.updated"
EVENT_TICKET_VERIFIED = "ticket.verified"
EVENT_TICKET_SCORED = "ticket.scored"
EVENT_TICKET_QUALIFIED = "ticket.qualified"
EVENT_OUTREACH_STARTED = "outreach.started"
EVENT_OUTREACH_SENT = "outreach.sent"
EVENT_PROSPECT_REPLIED = "prospect.replied"
EVENT_HANDOVER_CREATED = "handover.created"
EVENT_DEAL_CREATED = "deal.created"
EVENT_DEAL_UPDATED = "deal.updated"
EVENT_CONNECTOR_STARTED = "connector.started"
EVENT_CONNECTOR_FAILED = "connector.failed"
EVENT_CONNECTOR_COMPLETED = "connector.completed"
EVENT_AI_RUN_STARTED = "ai.run.started"
EVENT_AI_RUN_COMPLETED = "ai.run.completed"
EVENT_QA_FINDING_CREATED = "qa.finding.created"
EVENT_CHANGE_REQUEST_CREATED = "change.request.created"

CHANNEL = "leadsynt:events"


class EventBus:
    _subscribers: dict[str, list[Callable[[str, dict], None]]] = {}
    _lock = threading.Lock()
    _redis_client = None
    _redis_checked = False

    @classmethod
    def on(cls, event: str, handler: Callable[[str, dict], None]) -> Callable:
        with cls._lock:
            cls._subscribers.setdefault(event, []).append(handler)
        return handler

    @classmethod
    def off(cls, event: str, handler: Callable) -> None:
        with cls._lock:
            if event in cls._subscribers:
                cls._subscribers[event] = [h for h in cls._subscribers[event] if h is not handler]

    @classmethod
    def _get_redis(cls):
        if cls._redis_checked:
            return cls._redis_client
        cls._redis_checked = True
        try:
            import redis as _redis

            from app.core.config import get_settings

            client = _redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=1, socket_timeout=1)
            client.ping()
            cls._redis_client = client
        except Exception:  # noqa: BLE001 — in-process fallback is by design
            logger.debug("redis unavailable; event bus running in-process only")
            cls._redis_client = None
        return cls._redis_client

    @classmethod
    def publish(cls, event: str, payload: dict[str, Any]) -> None:
        """Publish to in-process subscribers and (best effort) Redis pub/sub."""
        for handler in list(cls._subscribers.get(event, [])) + list(cls._subscribers.get("*", [])):
            try:
                handler(event, payload)
            except Exception:  # noqa: BLE001 — one bad subscriber must not break flow
                logger.exception("event handler failed for %s", event)
        client = cls._get_redis()
        if client is not None:
            try:
                client.publish(CHANNEL, json.dumps({"event": event, "payload": payload}, default=str))
            except Exception:  # noqa: BLE001
                logger.warning("redis publish failed for %s", event)
