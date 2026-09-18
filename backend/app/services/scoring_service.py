"""Scoring service — deterministic, explainable, snapshot-based.

The rule engine is the foundation scoring path (no AI, no guessing): every
factor is recorded in the snapshot's ``factors`` payload so any score can be
explained and audited. The Lead Scoring AI agent (later phase) plugs into the
same snapshot tables with ``computed_by`` = its agent id.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enums import Freshness, IntentLevel, ScoreKind, TicketStatus, VerificationStatus
from app.models.scoring import IntentScoreSnapshot, LeadScoreSnapshot, RiskScoreSnapshot
from app.models.ticket import Ticket

_INTENT_WEIGHT = {IntentLevel.CRITICAL: 40, IntentLevel.HIGH: 30, IntentLevel.MEDIUM: 20, IntentLevel.LOW: 10}
_URGENCY_WEIGHT = {"NOW": 20, "WEEK": 15, "MONTH": 10, "UNKNOWN": 0}
_FRESHNESS_WEIGHT = {Freshness.FRESH: 15, Freshness.AGING: 8, Freshness.STALE: 0}


def _clamp(value: float) -> int:
    return max(0, min(100, int(round(value))))


def compute_scores(ticket: Ticket) -> dict:
    """Return lead/intent/risk scores + factors + confidence for a ticket."""
    factors: dict[str, float] = {}

    # --- intent -------------------------------------------------------------
    intent = 0.0
    if ticket.intent_level:
        intent += _INTENT_WEIGHT[ticket.intent_level]
        factors["intent_level"] = _INTENT_WEIGHT[ticket.intent_level]
    urgency = (ticket.urgency or "UNKNOWN").upper()
    intent += _URGENCY_WEIGHT.get(urgency, 0)
    factors["urgency"] = _URGENCY_WEIGHT.get(urgency, 0)
    if ticket.budget is not None:
        intent += 10
        factors["budget_present"] = 10
    if ticket.lead_score is None and ticket.discovered_at is not None:
        age_hours = (datetime.now(timezone.utc) - ticket.discovered_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        if age_hours <= 48:
            intent += 10
            factors["fresh_discovery"] = 10
    intent = _clamp(intent)

    # --- lead (composite) -----------------------------------------------------
    lead = 0.0
    lead += intent * 0.5
    factors["intent_component"] = round(intent * 0.5, 2)
    if ticket.verification_status == VerificationStatus.VERIFIED:
        lead += 15
        factors["verified"] = 15
    lead += _FRESHNESS_WEIGHT.get(ticket.freshness, 0)
    factors["freshness"] = _FRESHNESS_WEIGHT.get(ticket.freshness, 0)
    if ticket.budget is not None:
        lead += 15
        factors["budget"] = 15
    if ticket.requirement and len(ticket.requirement) >= 80:
        lead += 10
        factors["requirement_detail"] = 10
    if ticket.type is not None:
        lead += 5
        factors["classified_type"] = 5
    lead = _clamp(lead)

    # --- risk -------------------------------------------------------------------
    risk = 5.0
    risk_f = {"base": 5.0}
    if ticket.verification_status in (VerificationStatus.UNVERIFIED, VerificationStatus.UNKNOWN):
        risk += 15
        risk_f["unverified"] = 15
    if ticket.duplicate_status in ("POSSIBLE_DUPLICATE", "DUPLICATE"):
        risk += 15
        risk_f["duplicate_signal"] = 15
    if not ticket.original_url and not ticket.platform_url:
        risk += 10
        risk_f["no_source_url"] = 10
    if ticket.discovered_at is None:
        risk += 5
        risk_f["no_discovery_timestamp"] = 5
    risk = _clamp(risk)

    # --- confidence: how much of the picture is known ---------------------------
    known = sum(
        1
        for present in (
            ticket.intent_level, ticket.urgency, ticket.budget,
            ticket.verification_status == VerificationStatus.VERIFIED,
            ticket.requirement, ticket.original_url,
        )
        if present
    )
    confidence = round(known / 6, 2)

    return {
        "lead": lead,
        "intent": intent,
        "risk": risk,
        "confidence": confidence,
        "factors": {
            "lead": factors,
            "intent": factors,
            "risk": risk_f,
        },
    }


def score_ticket(
    db: Session,
    ticket: Ticket,
    *,
    computed_by: str = "rule-engine",
    agent_run_id: str | None = None,
) -> dict:
    """Compute + persist scores. Snapshots are immutable; ticket carries the
    latest values. Returns the scoring summary."""
    result = compute_scores(ticket)
    now = datetime.now(timezone.utc)

    for model, kind, value in (
        (LeadScoreSnapshot, ScoreKind.LEAD, result["lead"]),
        (IntentScoreSnapshot, ScoreKind.INTENT, result["intent"]),
        (RiskScoreSnapshot, ScoreKind.RISK, result["risk"]),
    ):
        db.add(
            model(
                kind=kind,
                ticket_id=ticket.id,
                score=int(value),
                confidence=result["confidence"],
                factors=result["factors"],
                agent_run_id=agent_run_id,
                computed_by=computed_by,
            )
        )

    ticket.lead_score = int(result["lead"])
    ticket.intent_score = int(result["intent"])
    ticket.risk_score = int(result["risk"])
    ticket.confidence = result["confidence"]
    ticket.last_activity_at = now

    # Qualification hint (does not auto-transition; humans/AI decide later)
    if ticket.status is not None and ticket.status.code in (
        TicketStatus.PROCESSING.value, TicketStatus.VERIFIED.value
    ) and result["lead"] >= 70:
        result["qualification_hint"] = "lead_score >= 70 — consider QUALIFIED"
    return result
