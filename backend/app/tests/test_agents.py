"""AI agent framework tests: registry completeness + run tracking."""

from app.agents.lead_scoring import LeadScoringAgent
from app.agents.registry import AGENTS, ensure_agents_seeded


def test_registry_has_all_12_agents():
    ids = {a.agent_id for a in AGENTS}
    expected = {
        "scout-ai", "market-intelligence-ai", "extraction-ai", "intent-ai",
        "entity-resolution-ai", "verification-ai", "enrichment-ai",
        "fraud-authenticity-ai", "lead-scoring-ai", "outreach-ai",
        "handover-ai", "qa-master-ai",
    }
    assert ids == expected


def test_registry_fields_complete():
    for a in AGENTS:
        assert a.agent_id and a.name and a.version
        assert a.purpose
        assert a.system_instructions
        assert a.allowed_tools
        assert a.input_schema
        assert a.output_schema
        assert a.confidence_requirements
        assert a.evidence_requirements


def test_agents_endpoint_lists_registry(client, admin_headers):
    r = client.get("/api/v1/agents", headers=admin_headers)
    assert r.status_code == 200
    agents = r.json()["data"]
    assert len(agents) == 12
    qa = next(a for a in agents if a["agent_id"] == "qa-master-ai")
    assert "change-control" in qa["system_instructions"].lower() or "approval" in qa["system_instructions"].lower()
    assert qa["total_runs"] >= 0


def test_agent_run_recorded_with_history(db_session, create_ticket, client, operator_headers):
    t = create_ticket()
    db = db_session
    agent = LeadScoringAgent(db)
    run = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="lead-scoring")
    db.commit()
    assert run.status.value == "COMPLETED"
    assert run.output["lead"] is not None
    assert 0 <= run.confidence <= 1
    assert run.cost_usd == 0.0
    # evidence attached
    from app.models.ai import AIEvidence

    ev = db.query(AIEvidence).filter(AIEvidence.run_id == run.id).all()
    assert len(ev) >= 1
    # agent totals incremented
    from app.models.ai import AIAgent

    agent_row = db.get(AIAgent, run.agent_id)
    assert agent_row.total_runs >= 1
    # audit trail
    from app.models.ops import AuditLog

    logs = db.query(AuditLog).filter(
        AuditLog.action == "ai.run.completed:lead-scoring-ai",
        AuditLog.resource_id == run.id,
    ).all()
    assert len(logs) == 1


def test_agent_run_failure_recorded(db_session, client, operator_headers, create_ticket):
    db = db_session
    agent = LeadScoringAgent(db)
    run = agent.run(payload={"ticket_id": "no-such-ticket"}, kind="lead-scoring")
    db.commit()
    assert run.status.value == "FAILED"
    assert run.error
