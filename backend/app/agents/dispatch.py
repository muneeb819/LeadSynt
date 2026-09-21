"""Agent dispatch: agent_id -> concrete agent class.

Registry rows define *what* each agent is; this maps them to *implementations*
so the API and workers can trigger runs by id.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.agents.base import AgentBase
from app.agents.enrichment import EnrichmentAgent
from app.agents.entity_resolution import EntityResolutionAgent
from app.agents.extraction import ExtractionAgent
from app.agents.fraud import FraudAuthenticityAgent
from app.agents.intent import IntentAgent
from app.agents.lead_scoring import LeadScoringAgent
from app.agents.outreach import OutreachAgent
from app.agents.verification import VerificationAgent
from app.core.exceptions import NotFoundError

IMPLEMENTED_AGENTS: dict[str, type[AgentBase]] = {
    "extraction-ai": ExtractionAgent,
    "intent-ai": IntentAgent,
    "verification-ai": VerificationAgent,
    "enrichment-ai": EnrichmentAgent,
    "fraud-authenticity-ai": FraudAuthenticityAgent,
    "entity-resolution-ai": EntityResolutionAgent,
    "lead-scoring-ai": LeadScoringAgent,
    "outreach-ai": OutreachAgent,
}


def get_agent(db: Session, agent_id: str) -> AgentBase:
    cls = IMPLEMENTED_AGENTS.get(agent_id)
    if cls is None:
        raise NotFoundError(f"Agent has no executable implementation: {agent_id}")
    return cls(db)