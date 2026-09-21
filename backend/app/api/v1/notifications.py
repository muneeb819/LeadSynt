"""Notifications API (in-app channel)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.ops import Notification
from app.schemas.common import Envelope

router = APIRouter()


@router.get("", response_model=Envelope)
def list_notifications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    filters = [Notification.user_id == user.id]
    if unread_only:
        filters.append(Notification.is_read == False)
    total = db.execute(
        select(func.count()).select_from(Notification).where(*filters)
    ).scalar_one()
    rows = db.execute(
        select(Notification).where(*filters).order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return Envelope(data={
        "items": [
            {
                "id": n.id, "type": n.type.value, "title": n.title, "body": n.body,
                "ticket_id": n.ticket_id, "is_read": n.is_read,
                "created_at": n.created_at.isoformat() if n.created_at else None,
            }
            for n in rows
        ],
        "pagination": {"page": page, "page_size": page_size, "total": total,
                       "total_pages": (total + page_size - 1) // page_size},
    })


@router.post("/{notification_id}/read", response_model=Envelope)
def mark_read(
    notification_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from datetime import datetime, timezone

    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        from app.core.exceptions import NotFoundError

        raise NotFoundError("Notification not found")
    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.now(timezone.utc)
        db.commit()
    return Envelope(data={"id": n.id, "is_read": True})
