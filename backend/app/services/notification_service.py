"""Notification service (in-app now; email/SMS plug in later).

Providers are gated by settings: if a channel provider is not configured the
event is recorded (audit-able) but delivery is marked ``skipped`` — no
silent failures.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enums import NotificationChannel, NotificationType
from app.models.ops import Notification

logger = logging.getLogger("leadsynt.notifications")


def notify(
    db: Session,
    *,
    user_id: str,
    type: NotificationType,
    title: str,
    body: str | None = None,
    ticket_id: str | None = None,
    channel: NotificationChannel = NotificationChannel.IN_APP,
) -> Notification:
    n = Notification(
        user_id=user_id,
        channel=channel,
        type=type,
        title=title,
        body=body,
        ticket_id=ticket_id,
    )
    db.add(n)
    db.flush()
    s = get_settings()
    if channel is NotificationChannel.EMAIL and not s.notifications_email:
        logger.info("email notification skipped (provider not configured)", extra={"user_id": user_id})
    if channel is NotificationChannel.SMS and not s.notifications_sms:
        logger.info("sms notification skipped (provider not configured)", extra={"user_id": user_id})
    return n


def notify_ticket_owner(
    db: Session,
    *,
    ticket_id: str,
    owner_id: str | None,
    type: NotificationType,
    title: str,
    body: str | None = None,
    **kwargs: Any,
) -> Notification | None:
    if not owner_id:
        return None
    return notify(
        db, user_id=owner_id, type=type, title=title, body=body,
        ticket_id=ticket_id, **kwargs,
    )


def unread_count(db: Session, user_id: str) -> int:
    from sqlalchemy import func

    return db.execute(
        select(func.count()).select_from(Notification).where(
            Notification.user_id == user_id, Notification.is_read == False
        )
    ).scalar_one()
