"""Admin API: audit logs + change requests (change-control pipeline)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.enums import ChangeRequestStatus
from app.models.ops import AuditLog, ChangeRequest
from app.schemas.common import Envelope
from app.services.audit_service import audit
from app.queues.events import EVENT_CHANGE_REQUEST_CREATED, EventBus

router = APIRouter()


@router.get("/audit", response_model=Envelope)
def audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    user=Depends(require_permission("audit:read")),
    db: Session = Depends(get_db),
):
    filters = []
    if action:
        filters.append(AuditLog.action == action)
    if resource_type:
        filters.append(AuditLog.resource_type == resource_type)
    rows = db.execute(
        select(AuditLog).where(*filters).order_by(AuditLog.timestamp.desc()).limit(limit)
    ).scalars().all()
    return Envelope(data=[
        {
            "id": r.id, "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "actor_id": r.actor_id, "actor_type": r.actor_type, "action": r.action,
            "resource_type": r.resource_type, "resource_id": r.resource_id,
            "before": r.before, "after": r.after, "meta": r.meta,
        }
        for r in rows
    ])


class ChangeRequestIn(BaseModel):
    kind: str = Field(pattern="^(code|config|database|deploy)$")
    summary: str = Field(min_length=5, max_length=300)
    description: str | None = None
    plan: dict | None = None


@router.post("/change-requests", status_code=201, response_model=Envelope)
def create_change_request(
    payload: ChangeRequestIn,
    user=Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
):
    cr = ChangeRequest(
        kind=payload.kind, summary=payload.summary, description=payload.description,
        plan=payload.plan, status=ChangeRequestStatus.PROPOSED, requested_by=user.id,
    )
    db.add(cr)
    db.flush()
    audit(db, action="change.request.created", actor_id=user.id, actor_type="user",
          resource_type="change_request", resource_id=cr.id,
          after={"kind": cr.kind, "summary": cr.summary})
    EventBus.publish(EVENT_CHANGE_REQUEST_CREATED, {"change_request_id": cr.id})
    db.commit()
    return Envelope(data={"id": cr.id, "status": cr.status.value})


@router.post("/change-requests/{cr_id}/approve", response_model=Envelope)
def approve_change_request(
    cr_id: str,
    user=Depends(require_permission("admin:full")),
    db: Session = Depends(get_db),
):
    cr = db.get(ChangeRequest, cr_id)
    if cr is None:
        raise NotFoundError("Change request not found")
    if cr.status not in (ChangeRequestStatus.PROPOSED, ChangeRequestStatus.PLAN_READY):
        raise BadRequestError("Change request is not in an approvable state")
    cr.status = ChangeRequestStatus.APPROVED
    cr.approved_by = user.id
    audit(db, action="change.request.approved", actor_id=user.id, actor_type="user",
          resource_type="change_request", resource_id=cr.id)
    db.commit()
    return Envelope(data={"id": cr.id, "status": cr.status.value})
