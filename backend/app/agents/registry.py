"""Registry of LeadSynt's specialized agents.

Foundation state: all 12 agents are DEFINED (id, version, purpose, system
instructions, allowed tools, schemas, confidence/evidence requirements) and
seeded as rows in ``ai_agents``. Their execution logic is implemented
incrementally; the first agents (Lead Scoring, QA Master) already run with
deterministic engines behind this same interface.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentSpec
from app.models.ai import AIAgent
from app.models.enums import AgentStatus

TICKET_INPUT = {
    "type": "object",
    "properties": {"ticket_id": {"type": "string"}},
    "required": ["ticket_id"],
}
TICKET_OUTPUT = {
    "type": "object",
    "properties": {
        "ticket_id": {"type": "string"},
        "decision": {"type": "string"},
        "confidence": {"type": "number"},
        "evidence": {"type": "array"},
        "rationale": {"type": "string"},
    },
}

EVIDENCE_RULE = "Every claim must cite a source URL, record id, or stored field. No citations -> confidence capped at 0.4."
NO_INVENT_RULE = "Never invent missing information. Unverifiable fields must be reported as UNKNOWN/UNVERIFIED."

AGENTS: list[AgentSpec] = [
    AgentSpec(
        agent_id="scout-ai", name="Scout AI", version="1.0.0",
        purpose="Scan authorized sources for new business signals (opportunities, requirements, buyers, sellers, RFPs).",
        system_instructions="Discover signals only from authorized, permitted sources. Record provenance (URL, platform, timestamp) for every signal. Never bypass CAPTCHA, auth, paywalls or anti-bot controls.",
        allowed_tools=("source.read", "source.fetch_permitted", "ticket.propose"),
        input_schema={"type": "object", "properties": {"source_ids": {"type": "array", "items": {"type": "string"}}}},
        output_schema={"type": "object", "properties": {"signals": {"type": "array"}}},
        confidence_requirements="Confidence >= 0.6 requires a fetchable source URL and timestamp.",
        evidence_requirements=EVIDENCE_RULE,
    ),
    AgentSpec(
        agent_id="market-intelligence-ai", name="Market Intelligence AI", version="1.0.0",
        purpose="Analyze market context: sectors, regions, demand trends, competitive landscape around a ticket.",
        system_instructions="Summarize market context with cited sources only. Distinguish observed facts from inferences and label inferences as such.",
        allowed_tools=("source.read", "market.stats"),
        input_schema=TICKET_INPUT,
        output_schema={"type": "object", "properties": {"sector_outlook": {"type": "string"}, "signals": {"type": "array"}}},
        confidence_requirements="Confidence reflects source recency and agreement across sources.",
        evidence_requirements=EVIDENCE_RULE,
    ),
    AgentSpec(
        agent_id="extraction-ai", name="Extraction AI", version="1.0.0",
        purpose="Extract structured fields (requirement, budget, timeline, contacts) from raw source content.",
        system_instructions="Extract only what the source states. Each extracted field carries its span/URL. Missing fields become UNKNOWN — never guessed.",
        allowed_tools=("source.read", "text.extract"),
        input_schema={"type": "object", "properties": {"source_record_id": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"fields": {"type": "object"}, "unknowns": {"type": "array"}}},
        confidence_requirements="Per-field confidence; aggregate >= 0.7 to accept without review.",
        evidence_requirements="Each field must reference the exact source span or URL.",
    ),
    AgentSpec(
        agent_id="intent-ai", name="Intent AI", version="1.0.0",
        purpose="Classify buyer intent level and urgency from ticket content and conversation history.",
        system_instructions="Classify intent as LOW/MEDIUM/HIGH/CRITICAL with rationale. Use only stored ticket + conversation data.",
        allowed_tools=("ticket.read", "conversation.read"),
        input_schema=TICKET_INPUT,
        output_schema={"type": "object", "properties": {"intent_level": {"type": "string"}, "urgency": {"type": "string"}, "rationale": {"type": "string"}}},
        confidence_requirements="Confidence >= 0.65 requires at least two distinct intent signals.",
        evidence_requirements=EVIDENCE_RULE + " " + NO_INVENT_RULE,
    ),
    AgentSpec(
        agent_id="entity-resolution-ai", name="Entity Resolution AI", version="1.0.0",
        purpose="Resolve and merge entities (people, companies, domains) across sources; flag duplicates.",
        system_instructions="Match entities using exact fields first, then fuzzy with explicit threshold. Produce merge proposals, never auto-merge without review.",
        allowed_tools=("entity.read", "entity.propose_merge"),
        input_schema={"type": "object", "properties": {"entity_kind": {"type": "string"}, "entity_ref": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"matches": {"type": "array"}, "merge_proposals": {"type": "array"}}},
        confidence_requirements="Merge proposals below 0.9 require human confirmation.",
        evidence_requirements="Each match cites the compared field values.",
    ),
    AgentSpec(
        agent_id="verification-ai", name="Verification AI", version="1.0.0",
        purpose="Orchestrate verification: email (syntax/domain/MX/provider), phone, company identity, digital identity.",
        system_instructions="Run deterministic checks first; call providers only when configured. Store history, never overwrite. Unknown results stay UNKNOWN.",
        allowed_tools=("verification.email", "verification.phone", "verification.company", "dns.lookup_permitted"),
        input_schema={"type": "object", "properties": {"ticket_id": {"type": "string"}, "kinds": {"type": "array"}}},
        output_schema={"type": "object", "properties": {"results": {"type": "array"}}},
        confidence_requirements="VERIFIED requires a passing deterministic check AND a passing provider check when configured.",
        evidence_requirements="Every result records checks performed, provider, and raw evidence.",
    ),
    AgentSpec(
        agent_id="enrichment-ai", name="Enrichment AI", version="1.0.0",
        purpose="Enrich tickets/contacts/companies from authorized data (licensed datasets, permitted public data).",
        system_instructions="Enrich only from configured, permitted providers. Record provenance per field. Never fabricate enrichment values.",
        allowed_tools=("provider.enrich", "source.read"),
        input_schema=TICKET_INPUT,
        output_schema={"type": "object", "properties": {"fields": {"type": "object"}, "provenance": {"type": "object"}}},
        confidence_requirements="Each enriched field carries provider + fetch timestamp.",
        evidence_requirements=EVIDENCE_RULE + " " + NO_INVENT_RULE,
    ),
    AgentSpec(
        agent_id="fraud-authenticity-ai", name="Fraud & Authenticity AI", version="1.0.0",
        purpose="Detect fraud/authenticity risk: fake leads, spoofed sources, impersonation, recycled content.",
        system_instructions="Score risk with explainable factors (source reputation, consistency, age, duplication). Flag, never auto-kill; DISQUALIFY only above threshold with human-visible evidence.",
        allowed_tools=("ticket.read", "entity.read", "source.read"),
        input_schema=TICKET_INPUT,
        output_schema={"type": "object", "properties": {"risk_score": {"type": "number"}, "factors": {"type": "array"}}},
        confidence_requirements="Risk >= 80 requires >= 2 independent red flags.",
        evidence_requirements="Every red flag must cite the specific field/source.",
    ),
    AgentSpec(
        agent_id="lead-scoring-ai", name="Lead Scoring AI", version="1.0.0",
        purpose="Produce lead/intent/risk scores with full factor explainability and snapshot history.",
        system_instructions="Score 0-100 using declared factors only. Record all factors in the snapshot. Deterministic rule engine is the baseline; ML extensions must stay explainable.",
        allowed_tools=("ticket.read", "score.snapshot"),
        input_schema=TICKET_INPUT,
        output_schema={"type": "object", "properties": {"lead": {"type": "number"}, "intent": {"type": "number"}, "risk": {"type": "number"}, "factors": {"type": "object"}}},
        confidence_requirements="Confidence = fraction of scoring inputs actually known.",
        evidence_requirements="Snapshots must include the full factor breakdown.",
    ),
    AgentSpec(
        agent_id="outreach-ai", name="Outreach AI", version="1.0.0",
        purpose="Draft and schedule compliant outreach; ALWAYS check suppression before sending; stop on reply.",
        system_instructions="Check suppression/consent before any send. Personalize from verified ticket data only. On any qualifying reply, stop immediately and hand over to human.",
        allowed_tools=("outreach.draft", "outreach.schedule", "suppression.check", "ticket.read"),
        input_schema=TICKET_INPUT,
        output_schema={"type": "object", "properties": {"message": {"type": "string"}, "suppression_ok": {"type": "boolean"}}},
        confidence_requirements="suppression_ok must be TRUE from the live check, never assumed.",
        evidence_requirements="Every send records template, channel, suppression check result, timestamp.",
    ),
    AgentSpec(
        agent_id="handover-ai", name="Handover AI", version="1.0.0",
        purpose="Generate the human handover dossier on reply: context, history, sentiment, suggested next action.",
        system_instructions="Produce a complete dossier with exact timestamps and verbatim incoming message. Suggest one next action. Never continue automation after handover.",
        allowed_tools=("ticket.read", "conversation.read", "handover.propose"),
        input_schema=TICKET_INPUT,
        output_schema={"type": "object", "properties": {"dossier": {"type": "object"}, "suggested_next_action": {"type": "string"}}},
        confidence_requirements="Dossier is complete only when conversation history and outreach history are included.",
        evidence_requirements="Verbatim messages required; no paraphrasing of the incoming message.",
    ),
    AgentSpec(
        agent_id="qa-master-ai", name="QA Master AI", version="1.0.0",
        purpose="Continuous quality: inspect health, data quality, duplicates, stale tickets, failures, spikes; produce findings with evidence.",
        system_instructions="Inspect the system read-only. Produce findings with severity, evidence, root-cause hypothesis, recommended action, affected component, test recommendation. Never modify production; changes go through the change-control pipeline with approval.",
        allowed_tools=("system.read", "db.query_readonly", "logs.read", "qa.finding.propose", "change.request.propose"),
        input_schema={"type": "object", "properties": {"scope": {"type": "string"}}},
        output_schema={"type": "object", "properties": {"findings": {"type": "array"}, "summary": {"type": "string"}}},
        confidence_requirements="Findings cite concrete records/IDs as evidence; 'suspicion' without evidence is not a finding.",
        evidence_requirements="Severity >= HIGH requires reproducible evidence (record ids, counts, error text).",
    ),
]


def ensure_agents_seeded(db: Session) -> None:
    """Idempotently seed the agent registry rows."""
    from app.core.config import get_settings

    default_budget = get_settings().ai_default_monthly_budget_usd
    for spec in AGENTS:
        row = db.execute(select(AIAgent).where(AIAgent.agent_id == spec.agent_id)).scalar_one_or_none()
        if row is None:
            db.add(
                AIAgent(
                    agent_id=spec.agent_id,
                    name=spec.name,
                    version=spec.version,
                    purpose=spec.purpose,
                    system_instructions=spec.system_instructions,
                    allowed_tools=list(spec.allowed_tools),
                    input_schema=spec.input_schema,
                    output_schema=spec.output_schema,
                    confidence_requirements=spec.confidence_requirements,
                    evidence_requirements=spec.evidence_requirements,
                    status=AgentStatus.ACTIVE,
                    model=None,
                    monthly_budget_usd=default_budget,
                )
            )
    db.flush()
