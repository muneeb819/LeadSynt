"""Connectors API: list, health, trigger runs (scheduled runs via beat)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import NotFoundError
from app.models.source import ConnectorRun, SourceConnector
from app.schemas.common import Envelope

router = APIRouter()


class ConnectorOut(BaseModel):
    id: str
    connector_id: str
    source_id: str
    source_name: str
    status: str
    auth_method: str
    schedule_cron: str | None
    rate_limit_per_hour: int | None
    last_run_at: str | None
    last_success_at: str | None
    last_failure_at: str | None
    last_error: str | None
    health: str
    configuration: dict


def _out(c: SourceConnector) -> dict:
    return ConnectorOut(
        id=c.id, connector_id=c.connector_id, source_id=c.source_id,
        source_name=c.source.name if c.source else None, status=c.status,
        auth_method=c.auth_method.value, schedule_cron=c.schedule_cron,
        rate_limit_per_hour=c.rate_limit_per_hour,
        last_run_at=c.last_run_at.isoformat() if c.last_run_at else None,
        last_success_at=c.last_success_at.isoformat() if c.last_success_at else None,
        last_failure_at=c.last_failure_at.isoformat() if c.last_failure_at else None,
        last_error=c.last_error, health=c.health.value,
        configuration=c.configuration or {},
    ).model_dump()


@router.get("", response_model=Envelope)
def connectors(
    user=Depends(require_permission("sources:read")), db: Session = Depends(get_db)
):
    rows = db.execute(select(SourceConnector)).scalars().all()
    return Envelope(data=[_out(c) for c in rows])


@router.get("/health", response_model=Envelope)
def connector_health(
    user=Depends(require_permission("sources:read")), db: Session = Depends(get_db)
):
    rows = db.execute(select(SourceConnector)).scalars().all()
    return Envelope(data=[
        {"connector_id": c.connector_id, "health": c.health.value,
         "status": c.status,
         "last_success_at": c.last_success_at.isoformat() if c.last_success_at else None}
        for c in rows
    ])


@router.post("/{connector_key}/run", response_model=Envelope)
def trigger_run(
    connector_key: str,
    request: Request,
    user=Depends(require_permission("sources:run")),
    db: Session = Depends(get_db),
):
    """On-demand run executes in-process (idempotent). Scheduled runs go
    through the Celery worker (beat schedule)."""
    from app.services.connector_service import run_connector

    try:
        result = run_connector(db, connector_key=connector_key, trigger="manual")
        db.commit()
    except Exception:  # noqa: BLE001 — connector.run re-raises after bookkeeping
        db.commit()  # persist the failed-run bookkeeping
        result = {"connector": connector_key, "status": "FAILED",
                  "reason": "connector run failed (see connector_runs)"}
    return Envelope(data=result, request_id=getattr(request.state, "request_id", None))


@router.get("/{connector_key}/runs", response_model=Envelope)
def runs(
    connector_key: str,
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("sources:read")),
    db: Session = Depends(get_db),
):
    connector = db.execute(
        select(SourceConnector).where(SourceConnector.connector_id == connector_key)
    ).scalar_one_or_none()
    if connector is None:
        raise NotFoundError("Connector not found")
    rows = db.execute(
        select(ConnectorRun)
        .where(ConnectorRun.connector_id == connector.id)
        .order_by(ConnectorRun.created_at.desc())
        .limit(limit)
    ).scalars().all()
    return Envelope(data=[
        {
            "id": r.id, "status": r.status.value, "trigger": r.trigger,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "records_found": r.records_found, "tickets_created": r.tickets_created,
            "error": r.error,
        }
        for r in rows
    ])
