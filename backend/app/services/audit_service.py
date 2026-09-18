"""Audit service — every important operation leaves an audit trail row."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.ops import AuditLog


def audit(
    db: Session,
    *,
    action: str,
    actor_id: str | None = None,
    actor_type: str = "system",
    resource_type: str | None = None,
    resource_id: str | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    ip_address: str | None = None,
    request_id: str | None = None,
) -> AuditLog:
    log = AuditLog(
        timestamp=datetime.now(timezone.utc),
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        before=before,
        after=after,
        meta=meta,
        ip_address=ip_address,
        request_id=request_id,
    )
    db.add(log)
    db.flush()
    return log
