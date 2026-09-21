"""AI agents API: registry, runs, decisions, evidence, catalog, analytics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.ai.catalog import get_model_rows, get_provider_rows
from app.core.exceptions import NotFoundError
from app.models.ai import AIAgent, AIDecision, AIEvidence, AIModel, AIRun
from app.schemas.agents import AgentRunRequest
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
        "monthly_budget_usd": float(a.monthly_budget_usd or 0),
    }


def _run_out(r: AIRun) -> dict:
    return {
        "id": r.id, "status": r.status.value, "kind": r.kind,
        "ticket_id": r.ticket_id,
        "confidence": float(r.confidence) if r.confidence is not None else None,
        "tokens_in": r.tokens_in, "tokens_out": r.tokens_out,
        "cost_usd": float(r.cost_usd) if r.cost_usd is not None else None,
        "error": r.error, "output": r.output,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


@router.get("", response_model=Envelope)
def agents(
    user=Depends(require_permission("agents:read")), db: Session = Depends(get_db)
):
    rows = db.execute(select(AIAgent).order_by(AIAgent.agent_id)).scalars().all()
    return Envelope(data=[_agent_out(a) for a in rows])


@router.get("/providers", response_model=Envelope)
def providers(
    user=Depends(require_permission("agents:read")), db: Session = Depends(get_db)
):
    rows = get_provider_rows(db)
    return Envelope(data=[
        {
            "id": p.id, "provider_id": p.provider_id, "name": p.name,
            "kind": p.kind, "base_url": p.base_url, "api_key_env": p.api_key_env,
            "is_default": p.is_default, "enabled": p.enabled,
            "model_count": db.execute(
                select(func.count()).select_from(AIModel).where(AIModel.provider_id == p.id)
            ).scalar_one(),
        }
        for p in rows
    ])


@router.get("/models", response_model=Envelope)
def models(
    user=Depends(require_permission("agents:read")), db: Session = Depends(get_db)
):
    rows = get_model_rows(db)
    provider_ids = {p.id: p.provider_id for p in get_provider_rows(db)}
    return Envelope(data=[
        {
            "id": m.id, "model_id": m.model_id, "provider_id": provider_ids.get(m.provider_id),
            "display_name": m.display_name, "context_window": m.context_window,
            "input_price_per_mtok": float(m.input_price_per_mtok or 0),
            "output_price_per_mtok": float(m.output_price_per_mtok or 0),
            "enabled": m.enabled,
        }
        for m in rows
    ])


@router.get("/analytics", response_model=Envelope)
def agent_analytics(
    user=Depends(require_permission("agents:read")), db: Session = Depends(get_db)
):
    """Per-agent dashboard: run stats, budget usage, and 7-day activity."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=6)

    items = []
    for a in db.execute(select(AIAgent).order_by(AIAgent.agent_id)).scalars().all():
        total = db.execute(select(func.count()).select_from(AIRun).where(AIRun.agent_id == a.id)).scalar_one()
        completed = db.execute(
            select(func.count()).select_from(AIRun).where(AIRun.agent_id == a.id, AIRun.status == "COMPLETED")
        ).scalar_one()
        failed = db.execute(
            select(func.count()).select_from(AIRun).where(AIRun.agent_id == a.id, AIRun.status == "FAILED")
        ).scalar_one()
        cancelled = db.execute(
            select(func.count()).select_from(AIRun).where(AIRun.agent_id == a.id, AIRun.status == "CANCELLED")
        ).scalar_one()
        total_cost = db.execute(
            select(func.coalesce(func.sum(AIRun.cost_usd), 0)).where(AIRun.agent_id == a.id)
        ).scalar_one()
        avg_conf = db.execute(
            select(func.avg(AIRun.confidence)).where(AIRun.agent_id == a.id, AIRun.status == "COMPLETED")
        ).scalar_one()
        last_finished = db.execute(
            select(AIRun.finished_at).where(AIRun.agent_id == a.id)
            .order_by(AIRun.finished_at.desc()).limit(1)
        ).scalar_one_or_none()
        month_spend = db.execute(
            select(func.coalesce(func.sum(AIRun.cost_usd), 0)).where(
                AIRun.agent_id == a.id, AIRun.status != "CANCELLED",
                AIRun.created_at >= month_start,
            )
        ).scalar_one()

        recent = db.execute(
            select(AIRun.created_at).where(AIRun.agent_id == a.id, AIRun.created_at >= week_start)
        ).scalars().all()
        trend: dict[str, int] = {}
        for ts in recent:
            day = ts.date().isoformat() if ts else None
            if day:
                trend[day] = trend.get(day, 0) + 1

        budget = float(a.monthly_budget_usd or 0)
        spent = float(month_spend or 0)
        items.append({
            "agent": _agent_out(a),
            "runs": {
                "total": total, "completed": completed, "failed": failed,
                "cancelled": cancelled,
                "avg_confidence": round(float(avg_conf), 4) if avg_conf is not None else None,
            },
            "cost": {"total_usd": float(total_cost or 0), "avg_per_run_usd": round(float(total_cost or 0) / total, 6) if total else 0.0},
            "budget": {
                "monthly_budget_usd": budget,
                "spent_this_month_usd": round(spent, 6),
                "remaining_usd": round(max(0.0, budget - spent), 6) if budget > 0 else None,
                "enforced": budget > 0,
            },
            "trend_7d": trend,
            "last_run_at": last_finished.isoformat() if last_finished else None,
        })

    grand_total_cost = db.execute(
        select(func.coalesce(func.sum(AIRun.cost_usd), 0))
    ).scalar_one()
    return Envelope(data={
        "items": items,
        "overall": {
            "agents": len(items),
            "runs": sum(i["runs"]["total"] for i in items),
            "failed": sum(i["runs"]["failed"] for i in items),
            "total_cost_usd": float(grand_total_cost or 0),
            "llm_configured": _llm_configured(db),
        },
        "generated_at": now.isoformat(),
    })


@router.post("/{agent_id}/run", response_model=Envelope)
def run_agent(
    agent_id: str,
    body: AgentRunRequest,
    user=Depends(require_permission("agents:run")),
    db: Session = Depends(get_db),
):
    from app.agents.dispatch import get_agent

    agent = get_agent(db, agent_id)
    payload = dict(body.payload or {})
    ticket_id = body.ticket_id or payload.get("ticket_id")
    if ticket_id:
        payload["ticket_id"] = ticket_id
    run = agent.run(payload=payload, ticket_id=ticket_id, kind=agent.spec.agent_id)
    db.commit()
    return Envelope(data=_run_out(run))


@router.get("/{agent_id}/runs", response_model=Envelope)
def agent_runs(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100),
    user=Depends(require_permission("agents:read")),
    db: Session = Depends(get_db),
):
    agent = db.get(AIAgent, agent_id)
    if agent is None:
        # agent_id may be the public slug â€” look up by slug
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


def _llm_configured(db: Session) -> bool:
    """True when a provider + model + key resolve at call time."""
    from app.ai.catalog import resolve_llm_config

    provider, model, key = resolve_llm_config(db)
    return provider is not None and model is not None and bool(key)
