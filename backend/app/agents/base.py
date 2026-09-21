"""AI agent architecture.

Every agent carries: unique agent id, name, version, purpose, system
instructions, allowed tools, input/output schemas, confidence + evidence
requirements, execution history (ai_runs), token/cost tracking, error
tracking and a full audit trail.

Hard rule: agents NEVER silently modify important business data. An agent
run produces an :class:`AgentResult`; applying a decision to business data
goes through services (which audit and enforce invariants).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai import AIAgent, AIEvidence, AIRun
from app.models.enums import RunStatus
from app.services.audit_service import audit


@dataclass(frozen=True, slots=True)
class AgentSpec:
    agent_id: str
    name: str
    version: str
    purpose: str
    system_instructions: str
    allowed_tools: tuple[str, ...]
    input_schema: dict
    output_schema: dict
    confidence_requirements: str
    evidence_requirements: str
    model: str | None = None


@dataclass(slots=True)
class AgentResult:
    status: str = "COMPLETED"  # COMPLETED | FAILED
    output: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    error: str | None = None


class AgentBase(ABC):
    """Interface all agents implement. ``run`` must be side-effect free on
    business data (it may only read and return a result)."""

    spec: AgentSpec

    def __init__(self, db: Session) -> None:
        self.db = db

    @abstractmethod
    def execute(self, payload: dict[str, Any]) -> AgentResult:
        """Deterministic/LLM logic. Must not mutate business rows."""

    def run(self, *, payload: dict[str, Any], ticket_id: str | None = None, kind: str | None = None) -> AIRun:
        """Execute + record the run (history, tokens, cost, errors)."""
        s = get_settings()
        run = AIRun(
            agent_id=self._agent_row_id(),
            ticket_id=ticket_id,
            kind=kind or self.spec.agent_id,
            status=RunStatus.RUNNING,
            input=payload,
            started_at=datetime.now(timezone.utc),
        )
        self.db.add(run)
        self.db.flush()
        # Phase A: monthly budget cap. Blocked runs are CANCELLED, never
        # charged, and never counted toward spend or totals.
        agent_row = self.db.get(AIAgent, run.agent_id)
        budget = float(agent_row.monthly_budget_usd or 0) if agent_row else 0.0
        if budget > 0 and self._monthly_spend_usd(run.agent_id) >= budget:
            run.status = RunStatus.CANCELLED
            run.error = f"monthly budget of {budget:.2f} USD exhausted"
            run.finished_at = datetime.now(timezone.utc)
            audit(
                self.db,
                action=f"ai.run.blocked:budget:{self.spec.agent_id}",
                actor_type="agent",
                actor_id=self.spec.agent_id,
                resource_type="ai_run",
                resource_id=run.id,
                after={"monthly_budget_usd": budget},
            )
            from app.queues.events import EventBus

            EventBus.publish("ai.run.blocked", {"run_id": run.id, "agent": self.spec.agent_id})
            self.db.flush()
            return run
        try:
            result = self.execute(payload)
        except Exception as exc:  # noqa: BLE001 — record, don't hide
            result = AgentResult(status="FAILED", error=str(exc))

        run.status = RunStatus.COMPLETED if result.status == "COMPLETED" else RunStatus.FAILED
        run.output = result.output
        run.confidence = result.confidence
        run.tokens_in = result.tokens_in
        run.tokens_out = result.tokens_out
        run.cost_usd = min(result.cost_usd, s.ai_max_cost_per_run_usd)
        run.error = result.error
        run.finished_at = datetime.now(timezone.utc)
        for ev in result.evidence:
            self.db.add(AIEvidence(run_id=run.id, kind=ev.get("kind", "snippet"),
                                   source_url=ev.get("source_url"), excerpt=ev.get("excerpt"),
                                   weight=ev.get("weight", 1.0)))
        agent = self.db.get(AIAgent, run.agent_id)
        if agent is not None:
            agent.total_runs += 1
            agent.total_cost_usd = float(agent.total_cost_usd or 0) + (run.cost_usd or 0)
        audit(
            self.db,
            action=f"ai.run.completed:{self.spec.agent_id}" if result.status == "COMPLETED"
            else f"ai.run.failed:{self.spec.agent_id}",
            actor_type="agent",
            actor_id=self.spec.agent_id,
            resource_type="ai_run",
            resource_id=run.id,
            after={"confidence": result.confidence, "error": result.error},
        )
        from app.queues.events import EventBus

        EventBus.publish(
            "ai.run.completed" if result.status == "COMPLETED" else "ai.run.failed",
            {"run_id": run.id, "agent": self.spec.agent_id},
        )
        self.db.flush()
        return run

    def _monthly_spend_usd(self, agent_row_id: str) -> float:
        """Sum of this calendar month's charged (non-CANCELLED) run costs."""
        from datetime import datetime, timezone

        from sqlalchemy import func, select

        month_start = datetime.now(timezone.utc).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        total = self.db.execute(
            select(func.coalesce(func.sum(AIRun.cost_usd), 0)).where(
                AIRun.agent_id == agent_row_id,
                AIRun.status != RunStatus.CANCELLED,
                AIRun.created_at >= month_start,
            )
        ).scalar_one()
        return float(total or 0)

    def _agent_row_id(self) -> str:
        from sqlalchemy import select

        row = self.db.execute(
            select(AIAgent).where(AIAgent.agent_id == self.spec.agent_id)
        ).scalar_one_or_none()
        if row is None:  # registry not seeded in this session
            from app.agents.registry import ensure_agents_seeded

            ensure_agents_seeded(self.db)
            row = self.db.execute(
                select(AIAgent).where(AIAgent.agent_id == self.spec.agent_id)
            ).scalar_one_or_none()
        return row.id if row else self.spec.agent_id
