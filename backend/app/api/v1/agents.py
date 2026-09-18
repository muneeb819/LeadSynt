"""AI agents API: registry, runs, decisions, evidence."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import NotFoundError
from app.models.ai import AIAgent, AIDecision, AIEvidence, AIRun
from app.schemas.common import Envelope

router = APIRouter()


def _agent_out(a: AIAgent) -> dict:
    return {
        "id": a.id, "agent_id": a.agent_id, "name": a.name, "version": a.version,
        "purpose": a.purpose, "status": a.status.value, "model": a.model,
        "system_instructions": a.system_instructions,
        "allowed_tools": a.allowed_tools, "input_schema": a.input_schema,
        "output_schema": a.output_schema,
        "confidence_requirements": a.confidence_requirements,
        "evidence_requirements": a.evidence_requirements,
        "total_runs": a.total_runs,
        "total_cost_usd": float(a.total_cost_usd or 0),
        "max_cost_usd_per_run": float(a.max_cost_usd_per_run or 0),
    }


@router.get("", response_model=Envelope)
def agents(
    user=Depends(require_permission("agents:read")), db: Session = Depends(get_db)
):
    rows = db.execute(select(AIAgent).order_by(AIAgent.agent_id)).scalars().all()
    return Envelope(data=[_agent_out(a) for a in rows])


@router.get("/{agent_id}/runs", response_model=Envelope)
def agent_runs(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("agents:read")),
    db: Session = Depends(get_db),
):
    agent = db.get(AIAgent, agent_id)
    if agent is None:
        # agent_id may be the public slug — look up by slug
        agent = db.execute(select(AIAgent).where(AIAgent.agent_id == agent_id)).scalar_one_or_none()
    if agent is None:
        raise NotFoundError("Agent not found")
    rows = db.execute(
        select(AIRun).where(AIRun.agent_id == agent.id)
        .order_by(AIRun.created_at.desc()).limit(limit)
    ).scalars().all()
    return Envelope(data=[
        {
            "id": r.id, "status": r.status.value, "kind": r.kind,
            "ticket_id": r.ticket_id, "confidence": float(r.confidence) if r.confidence is not None else None,
            "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
            "cost_usd": float(r.cost_usd) if r.cost_usd is not None else None,
            "error": r.error, "output": r.output,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in rows
    ])


@router.get("/{agent_id}/runs/{run_id}/evidence", response_model=Envelope)
def run_evidence(
    agent_id: str,
    run_id: str,
    user=Depends(require_permission("agents:read")),
    db: Session = Depends(get_db),
):
    rows = db.execute(select(AIEvidence).where(AIEvidence.run_id == run_id)).scalars().all()
    return Envelope(data=[
        {"id": e.id, "kind": e.kind, "source_url": e.source_url,
         "excerpt": e.excerpt, "weight": float(e.weight or 1.0)}
        for e in rows
    ])


@router.get("/{agent_id}/decisions", response_model=Envelope)
def decisions(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("agents:read")),
    db: Session = Depends(get_db),
):
    agent = db.execute(select(AIAgent).where(AIAgent.agent_id == agent_id)).scalar_one_or_none()
    if agent is None:
        raise NotFoundError("Agent not found")
    rows = db.execute(
        select(AIDecision).where(AIDecision.agent_id == agent.id)
        .order_by(AIDecision.created_at.desc()).limit(limit)
    ).scalars().all()
    return Envelope(data=[
        {"id": d.id, "decision": d.decision, "rationale": d.rationale,
         "confidence": float(d.confidence) if d.confidence is not None else None,
         "applied": d.applied, "run_id": d.run_id}
        for d in rows
    ])
