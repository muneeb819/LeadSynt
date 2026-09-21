"""Intent AI — Phase A implementation (deterministic signal engine).

Classifies buyer intent + urgency from stored ticket data only. Confidence
>= 0.65 requires at least two distinct intent signals (per agent spec).
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentBase, AgentResult
from app.models.enums import IntentLevel
from app.models.ticket import Ticket

# (signal_id, weight, description)
SIGNALS: list[tuple[str, int, str]] = [
    ("declared_intent", 25, "ticket declares intent level"),
    ("budget_present", 25, "monetary budget is known"),
    ("detailed_requirement", 15, "requirement text is substantive"),
    ("declared_urgency", 10, "ticket declares urgency"),
    ("deal_size_known", 10, "deal size band is known"),
    ("multiple_contacts", 10, "more than one contact linked"),
    ("primary_contact", 5, "at least one contact linked"),
    ("location_known", 5, "location/jurisdiction known"),
]


def _level_for(score: int) -> str:
    if score >= 80:
        return IntentLevel.CRITICAL.value
    if score >= 60:
        return IntentLevel.HIGH.value
    if score >= 35:
        return IntentLevel.MEDIUM.value
    return IntentLevel.LOW.value


class IntentAgent(AgentBase):
    from app.agents.registry import AGENTS

    spec = next(a for a in AGENTS if a.agent_id == "intent-ai")

    def _score(self, ticket: Ticket) -> tuple[list[str], int]:
        used: list[str] = []
        for signal_id, weight, _desc in SIGNALS:
            hit = False
            if signal_id == "declared_intent" and ticket.intent_level in (
                IntentLevel.HIGH, IntentLevel.CRITICAL,
            ):
                hit = True
            elif signal_id == "budget_present" and (ticket.budget or 0) > 0:
                hit = True
            elif signal_id == "detailed_requirement" and len(ticket.requirement or "") >= 40:
                hit = True
            elif signal_id == "declared_urgency" and ticket.urgency:
                hit = True
            elif signal_id == "deal_size_known" and ticket.deal_size:
                hit = True
            elif signal_id == "multiple_contacts" and len(ticket.ticket_contacts) >= 2:
                hit = True
            elif signal_id == "primary_contact" and len(ticket.ticket_contacts) == 1:
                hit = True
            elif signal_id == "location_known" and (ticket.location or ticket.jurisdiction):
                hit = True
            if hit:
                used.append(signal_id)
        score = min(100, sum(weight for sid, weight, _ in SIGNALS if sid in used))
        return used, score

    def execute(self, payload: dict[str, Any]) -> AgentResult:
        ticket_id = payload.get("ticket_id")
        ticket = self.db.get(Ticket, ticket_id) if ticket_id else None
        if ticket is None:
            return AgentResult(status="FAILED", error=f"ticket not found: {ticket_id}")

        used, score = self._score(ticket)
        level = _level_for(score)
        urgency = ticket.urgency
        if not urgency:
            urgency = "IMMEDIATE" if level == IntentLevel.CRITICAL.value else (
                "SOON" if level in {IntentLevel.HIGH.value, IntentLevel.MEDIUM.value} else "NORMAL"
            )
        available = len(SIGNALS)
        confidence = round(len(used) / available, 4)

        signals_detail = [{"signal": sid, "present": True} for sid in used]
        evidence = [
            {"kind": "record", "source_url": ticket.original_url,
             "excerpt": f"ticket {ticket.reference}"}
        ]
        return AgentResult(
            status="COMPLETED",
            output={
                "ticket_id": ticket_id,
                "intent_level": level,
                "intent_score": score,
                "urgency": urgency,
                "signals": signals_detail,
                "rationale": (
                    f"{len(used)} intent signals detected: {', '.join(used) or 'none'}; "
                    f"confidence {confidence:.2f} (requires >= 0.65 for auto-accept)"
                ),
            },
            confidence=confidence,
            evidence=evidence,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
        )