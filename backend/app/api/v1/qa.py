"""QA Master API: trigger sweeps, list runs/findings, manage finding status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.config import get_settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.enums import FindingStatus
from app.models.qa import QAFinding, QARun
from app.schemas.common import Envelope
from app.services.audit_service import audit
from app.services.qa_service import run_qa_sweep
from app.workers.tasks import qa_sweep_task

router = APIRouter()


class FindingStatusIn(BaseModel):
    status: str


@router.post("/sweep", response_model=Envelope)
def sweep(
    request: Request,
    user=Depends(require_permission("qa:run")),
    db: Session = Depends(get_db),
):
    """On-demand sweep runs in-process (deterministic DB scan).
    Scheduled sweeps run through the Celery worker (beat)."""
    result = run_qa_sweep(db, trigger="manual", actor_id=user.id)
    db.commit()
    return Envelope(data=result, request_id=getattr(request.state, "request_id", None))


@router.get("/runs", response_model=Envelope)
def runs(
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("qa:read")),
    db: Session = Depends(get_db),
):
    rows = db.execute(select(QARun).order_by(QARun.created_at.desc()).limit(limit)).scalars().all()
    return Envelope(data=[
        {
            "id": r.id, "trigger": r.trigger.value, "status": r.status,
            "summary": r.summary, "metrics": r.metrics,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ])


@router.get("/findings", response_model=Envelope)
def findings(
    status: str | None = None,
    severity: str | None = None,
    category: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    user=Depends(require_permission("qa:read")),
    db: Session = Depends(get_db),
):
    filters = []
    if status:
        filters.append(QAFinding.status == FindingStatus(status.upper()))
    if severity:
        filters.append(QAFinding.severity.value.upper() == severity.upper())
    if category:
        filters.append(QAFinding.category == category)
    rows = db.execute(select(QAFinding).where(*filters).order_by(QAFinding.created_at.desc()).limit(limit)).scalars().all()
    return Envelope(data=[
        {
            "id": f.id, "run_id": f.run_id, "category": f.category,
            "severity": f.severity.value, "title": f.title, "description": f.description,
            "evidence": f.evidence, "root_cause_hypothesis": f.root_cause_hypothesis,
            "recommended_action": f.recommended_action,
            "affected_component": f.affected_component,
            "test_recommendation": f.test_recommendation, "status": f.status.value,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in rows
    ])


@router.post("/findings/{finding_id}/status", response_model=Envelope)
def set_finding_status(
    finding_id: str,
    payload: FindingStatusIn,
    user=Depends(require_permission("qa:run")),
    db: Session = Depends(get_db),
):
    try:
        new_status = FindingStatus(payload.status.upper())
    except ValueError:
        raise BadRequestError(f"Unknown finding status: {payload.status}")
    f = db.get(QAFinding, finding_id)
    if f is None:
        raise NotFoundError("Finding not found")
    before = f.status.value
    f.status = new_status
    audit(db, action="qa.finding.status_changed", actor_id=user.id, actor_type="user",
          resource_type="qa_finding", resource_id=f.id,
          before={"status": before}, after={"status": new_status.value})
    db.commit()
    return Envelope(data={"id": f.id, "status": f.status.value})
