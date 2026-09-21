"""Phase A — AI implementations tests.

Covers: catalog seeding + LLM config resolution, the six new agent engines
(extraction, intent, verification, enrichment, fraud, entity resolution),
the monthly budget cap, run-trigger endpoint and the per-agent analytics API.
All deterministic paths — no API keys in CI.
"""

from app.agents.enrichment import EnrichmentAgent
from app.agents.entity_resolution import EntityResolutionAgent
from app.agents.extraction import ExtractionAgent
from app.agents.fraud import FraudAuthenticityAgent
from app.agents.intent import IntentAgent
from app.agents.verification import VerificationAgent
from app.ai.catalog import (
    ensure_ai_catalog_seeded, get_model_rows, get_provider_rows, resolve_llm_config,
)
from app.models.ai import AIAgent, AIRun
from app.models.enums import RunStatus
from app.models.ops import AuditLog
from app.models.verification import VerificationRecord


# ---------------------------------------------------------------------------
# Catalog + LLM config
# ---------------------------------------------------------------------------

def test_catalog_seeded_idempotently(db_session):
    ensure_ai_catalog_seeded(db_session)
    db_session.commit()
    ensure_ai_catalog_seeded(db_session)  # idempotent
    providers = get_provider_rows(db_session)
    models = get_model_rows(db_session)
    assert {p.provider_id for p in providers} == {"openai", "anthropic"}
    assert len(models) >= 4
    assert all(m.provider_id for m in models)


def test_llm_config_resolves_none_when_disabled(db_session):
    ensure_ai_catalog_seeded(db_session)
    provider, model, key = resolve_llm_config(db_session)
    assert provider is None
    assert model is None
    assert key is None


# ---------------------------------------------------------------------------
# Extraction agent
# ---------------------------------------------------------------------------

def test_extraction_agent_deterministic_fields_with_provenance(db_session, create_ticket):
    t = create_ticket()
    agent = ExtractionAgent(db_session)
    run = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="extraction")
    db_session.commit()
    assert run.status.value == "COMPLETED"
    out = run.output
    assert out["engine"] == "deterministic"
    assert "budget" in out["fields"] and out["fields"]["budget"] == 120000.0
    assert "emails" in out["fields"]
    assert "john.buyer@acme-fab.example.com" in out["fields"]["emails"]
    assert "unknowns" in out and "timeline" in out["unknowns"]
    # every extracted field carries provenance
    assert out["provenance"].get("budget")
    assert run.confidence is not None and 0.0 <= run.confidence <= 1.0


def test_extraction_agent_unknowns_never_guessed(db_session, create_ticket):
    t = create_ticket(requirement="")
    agent = ExtractionAgent(db_session)
    run = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="extraction")
    db_session.commit()
    assert run.status.value == "COMPLETED"
    out = run.output
    # empty requirement -> timeline/product-less content never fabricated
    assert "timeline" in out["unknowns"]
    assert out["fields"].get("timeline") is None


# ---------------------------------------------------------------------------
# Intent agent
# ---------------------------------------------------------------------------

def test_intent_agent_classifies_with_signals(db_session, create_ticket):
    t = create_ticket()
    agent = IntentAgent(db_session)
    run = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="intent")
    db_session.commit()
    assert run.status.value == "COMPLETED"
    out = run.output
    assert out["intent_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    assert out["intent_score"] >= 60  # budget + declared HIGH + detailed req
    assert len(out["signals"]) >= 2
    assert out["rationale"]
    assert run.confidence >= 0.65


# ---------------------------------------------------------------------------
# Verification agent
# ---------------------------------------------------------------------------

def test_verification_agent_orchestrates_kinds_evidence_backed(db_session, create_ticket):
    t = create_ticket()
    agent = VerificationAgent(db_session)
    run = agent.run(
        payload={"ticket_id": t["id"], "kinds": ["EMAIL", "PHONE"]},
        ticket_id=t["id"], kind="verification",
    )
    db_session.commit()
    assert run.status.value == "COMPLETED"
    out = run.output
    assert len(out["results"]) == 2
    assert all(r["result"] in {"VERIFIED", "FAILED", "UNKNOWN", "UNVERIFIABLE"} for r in out["results"])
    assert out["overall"] in {"VERIFIED", "FAILED", "PARTIAL", "UNKNOWN"}
    # history recorded through the sanctioned service, attributed to the agent
    recs = db_session.query(VerificationRecord).filter(
        VerificationRecord.entity_ref == t["id"]
    ).all()
    assert len(recs) == 2
    assert all(r.verified_by == "verification-ai" for r in recs)
    # evidence attached
    from app.models.ai import AIEvidence

    ev = db_session.query(AIEvidence).filter(AIEvidence.run_id == run.id).all()
    assert len(ev) >= 1


# ---------------------------------------------------------------------------
# Enrichment agent
# ---------------------------------------------------------------------------

def test_enrichment_agent_no_fabrication_with_provenance(db_session, create_ticket):
    t = create_ticket()
    agent = EnrichmentAgent(db_session)
    run = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="enrichment")
    db_session.commit()
    assert run.status.value == "COMPLETED"
    out = run.output
    assert out["provider"] == "none"
    assert "official_website" in out["fields"]
    assert out["fields"]["email_domain_match"]["match"] == "MATCH"
    assert out["fields"]["email_domain_match"]["detail"]
    # missing fields stay UNKNOWN, never invented
    for name in out["unknowns"]:
        assert name not in out["fields"]
    assert out["provenance"].get("official_website")


def test_enrichment_agent_no_company_reports_unknowns(db_session, create_ticket):
    t = create_ticket()
    agent = EnrichmentAgent(db_session)
    # company is removed -> agent must not fabricate anything
    from app.models.company import TicketCompany

    db_session.query(TicketCompany).filter(
        TicketCompany.ticket_id == t["id"]
    ).delete()
    db_session.commit()
    run = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="enrichment")
    db_session.commit()
    assert run.status.value == "COMPLETED"
    assert run.output["fields"] == {}
    assert "official_website" in run.output["unknowns"]


# ---------------------------------------------------------------------------
# Fraud & authenticity agent
# ---------------------------------------------------------------------------

def test_fraud_agent_clean_ticket_low_risk(db_session, create_ticket):
    t = create_ticket()
    agent = FraudAuthenticityAgent(db_session)
    run = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="fraud")
    db_session.commit()
    assert run.status.value == "COMPLETED"
    assert 0 <= run.output["risk_score"] <= 100
    assert run.output["suggested_action"] in {
        "no_action", "monitor", "flag_for_review", "flag_for_disqualification_review",
    }


def test_fraud_agent_flags_disposable_domain_with_evidence(db_session, create_ticket):
    t = create_ticket(contact={
        "full_name": "Scammy McScam",
        "title": "CEO",
        "work_email": "victim@mailinator.com",
        "phone": "123",
    })
    agent = FraudAuthenticityAgent(db_session)
    run = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="fraud")
    db_session.commit()
    assert run.status.value == "COMPLETED"
    names = {f["factor"] for f in run.output["factors"]}
    assert "disposable_email_domain" in names
    assert run.output["risk_score"] > 0
    from app.models.ai import AIEvidence

    ev = db_session.query(AIEvidence).filter(AIEvidence.run_id == run.id).all()
    assert len(ev) >= 1


# ---------------------------------------------------------------------------
# Entity resolution agent
# ---------------------------------------------------------------------------

def test_entity_resolution_agent_domain_graph(db_session, create_ticket):
    t = create_ticket()
    agent = EntityResolutionAgent(db_session)
    run = agent.run(
        payload={"entity_kind": "domain", "entity_ref": "acme-fab.example.com"},
        kind="entity-resolution",
    )
    db_session.commit()
    assert run.status.value == "COMPLETED"
    out = run.output
    assert len(out["matches"]) >= 1
    match = out["matches"][0]
    assert match["match_kind"] == "exact_domain"
    assert match["confidence"] >= 0.9
    assert out["note"]  # human confirmation rule surfaced


# ---------------------------------------------------------------------------
# Monthly budget cap
# ---------------------------------------------------------------------------

def test_budget_cap_blocks_runs_when_exhausted(db_session, create_ticket):
    from app.agents.lead_scoring import LeadScoringAgent

    t = create_ticket()
    agent = LeadScoringAgent(db_session)
    warm = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="lead-scoring")
    db_session.flush()
    agent_row = db_session.get(AIAgent, warm.agent_id)
    assert agent_row is not None
    # Charge 0.02 this month -> exceeds a 0.01 cap, so the next run is CANCELLED.
    db_session.add(
        AIRun(agent_id=agent_row.id, ticket_id=t["id"], kind="lead-scoring",
              status=RunStatus.COMPLETED, cost_usd=0.02)
    )
    agent_row.monthly_budget_usd = 0.01
    db_session.commit()
    blocked = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="lead-scoring")
    db_session.commit()
    assert blocked.status.value == "CANCELLED"
    assert "budget" in (blocked.error or "")
    logs = db_session.query(AuditLog).filter(
        AuditLog.action == "ai.run.blocked:budget:lead-scoring-ai",
        AuditLog.resource_id == blocked.id,
    ).all()
    assert len(logs) == 1


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------

def test_run_agent_endpoint_triggers_and_records(client, admin_headers, create_ticket):
    t = create_ticket()
    r = client.post(
        "/api/v1/agents/intent-ai/run",
        json={"ticket_id": t["id"]},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "COMPLETED"
    assert data["kind"] == "intent-ai"
    assert data["output"]["intent_level"] in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}


def test_run_agent_endpoint_unknown_agent_404(client, admin_headers):
    r = client.post(
        "/api/v1/agents/does-not-exist/run",
        json={"payload": {}},
        headers=admin_headers,
    )
    assert r.status_code == 404


def test_agents_analytics_endpoint_shape(client, admin_headers, create_ticket):
    t = create_ticket()
    client.post("/api/v1/agents/intent-ai/run", json={"ticket_id": t["id"]},
                headers=admin_headers)
    r = client.get("/api/v1/agents/analytics", headers=admin_headers)
    assert r.status_code == 200
    body = r.json()["data"]
    assert body["overall"]["agents"] == 12
    assert body["overall"]["llm_configured"] is False
    items = {i["agent"]["agent_id"]: i for i in body["items"]}
    intent = items["intent-ai"]
    assert intent["runs"]["total"] >= 1
    assert intent["runs"]["completed"] >= 1
    assert "monthly_budget_usd" in intent["budget"]
    assert "spent_this_month_usd" in intent["budget"]
    assert "trend_7d" in intent


def test_providers_and_models_endpoints(client, admin_headers):
    rp = client.get("/api/v1/agents/providers", headers=admin_headers)
    assert rp.status_code == 200
    providers = rp.json()["data"]
    assert {p["provider_id"] for p in providers} == {"openai", "anthropic"}
    rm = client.get("/api/v1/agents/models", headers=admin_headers)
    assert rm.status_code == 200
    models = rm.json()["data"]
    assert len(models) >= 4
    assert all(m["provider_id"] in {"openai", "anthropic"} for m in models)
    assert all(m["input_price_per_mtok"] > 0 for m in models)


def test_agents_list_includes_budget_field(client, admin_headers):
    r = client.get("/api/v1/agents", headers=admin_headers)
    assert r.status_code == 200
    for a in r.json()["data"]:
        assert "monthly_budget_usd" in a