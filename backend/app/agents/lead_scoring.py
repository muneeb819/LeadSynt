"""Concrete Lead Scoring Agent (foundation: deterministic rule engine).

Proves the agent framework end-to-end: run recording, confidence, evidence,
cost/token tracking. The agent READS the ticket and RETURNS scores — applying
them to the ticket is a separate, audited service call (agents never silently
mutate business data).
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentBase, AgentResult
from app.models.ticket import Ticket
from app.services.scoring_service import compute_scores


class LeadScoringAgent(AgentBase):
    from app.agents.registry import AGENTS

    spec = next(a for a in AGENTS if a.agent_id == "lead-scoring-ai")

    def execute(self, payload: dict[str, Any]) -> AgentResult:
        ticket_id = payload.get("ticket_id")
        ticket = self.db.get(Ticket, ticket_id)
        if ticket is None:
            return AgentResult(status="FAILED", error=f"ticket not found: {ticket_id}")
        result = compute_scores(ticket)
        return AgentResult(
            status="COMPLETED",
            output={
                "ticket_id": ticket_id,
                "lead": result["lead"],
                "intent": result["intent"],
                "risk": result["risk"],
                "factors": result["factors"],
            },
            confidence=result["confidence"],
            evidence=[{"kind": "record", "source_url": ticket.original_url,
                       "excerpt": f"ticket {ticket.reference}"}],
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
        )
