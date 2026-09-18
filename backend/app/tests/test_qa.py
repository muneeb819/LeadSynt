"""QA Master tests: deterministic findings with evidence; change control."""


def test_qa_sweep_flags_stale_ticket(client, admin_headers, create_ticket, db_session):
    from datetime import datetime, timedelta, timezone

    t = create_ticket()
    db = db_session
    from app.models.ticket import Ticket

    ticket = db.get(Ticket, t["id"])
    # force staleness: backdate discovery past the threshold
    ticket.discovered_at = datetime.now(timezone.utc) - timedelta(hours=200)
    db.commit()

    r = client.post("/api/v1/qa/sweep", headers=admin_headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["counts"].get("stale_tickets", 0) >= 1

    findings = client.get("/api/v1/qa/findings?category=data_quality",
                          headers=admin_headers).json()["data"]
    assert len(findings) >= 1
    f = findings[0]
    assert f["severity"] in ("MEDIUM", "HIGH", "CRITICAL", "LOW")
    assert f["evidence"]["count"] >= 1
    assert f["root_cause_hypothesis"]
    assert f["recommended_action"]
    assert f["test_recommendation"]


def test_qa_sweep_flags_ownerless_outreach_zone(client, admin_headers, create_ticket, db_session):
    t = create_ticket()
    for step in ["PROCESSING", "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED",
                 "OUTREACH_READY", "OUTREACH_ACTIVE"]:
        client.post(f"/api/v1/tickets/{t['id']}/status", json={"status": step},
                    headers=admin_headers)
    from app.models.ticket import Ticket

    ticket = db_session.get(Ticket, t["id"])
    ticket.owner_id = None
    db_session.commit()

    r = client.post("/api/v1/qa/sweep", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["data"]["counts"].get("ownerless_handover_zone", 0) >= 1


def test_finding_status_management(client, admin_headers, db_session):
    # create a finding via sweep (may be empty findings if clean)
    from app.models.qa import QARun, QAFinding
    from app.models.enums import FindingSeverity, FindingStatus

    run = QARun(trigger="MANUAL", status="COMPLETED")
    db_session.add(run)
    db_session.flush()
    f = QAFinding(run_id=run.id, category="test", severity=FindingSeverity.INFO,
                  title="test finding", status=FindingStatus.OPEN)
    db_session.add(f)
    db_session.commit()

    r = client.post(f"/api/v1/qa/findings/{f.id}/status",
                    json={"status": "ACKNOWLEDGED"}, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ACKNOWLEDGED"


def test_change_request_lifecycle(client, admin_headers):
    r = client.post("/api/v1/admin/change-requests", json={
        "kind": "config", "summary": "Raise hot-lead threshold to 90",
        "plan": {"key": "scoring", "value": {"hot_lead_threshold": 90}},
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    cr_id = r.json()["data"]["id"]
    assert r.json()["data"]["status"] == "PROPOSED"

    r2 = client.post(f"/api/v1/admin/change-requests/{cr_id}/approve",
                     headers=admin_headers)
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "APPROVED"


def test_change_request_requires_admin(client, operator_headers):
    r = client.post("/api/v1/admin/change-requests", json={
        "kind": "code", "summary": "attempt without admin",
    }, headers=operator_headers)
    assert r.status_code == 403
