"""Scoring tests: deterministic, bounded, snapshot-history, explainable."""


def test_score_bounds_and_factors(client, admin_headers, create_ticket, db_session):
    t = create_ticket()
    r = client.post(f"/api/v1/tickets/{t['id']}/score", headers=admin_headers)
    assert r.status_code == 200
    s = r.json()["data"]
    assert 0 <= s["lead"] <= 100
    assert 0 <= s["intent"] <= 100
    assert 0 <= s["risk"] <= 100
    assert 0 <= s["confidence"] <= 1
    assert "factors" in s and s["factors"]


def test_snapshots_are_immutable_history(client, admin_headers, create_ticket):
    t = create_ticket()
    client.post(f"/api/v1/tickets/{t['id']}/score", headers=admin_headers)
    client.post(f"/api/v1/tickets/{t['id']}/score", headers=admin_headers)
    r = client.get(f"/api/v1/scoring/snapshots/{t['id']}", headers=admin_headers)
    assert r.status_code == 200
    snaps = r.json()["data"]
    lead_snaps = [s for s in snaps if s["kind"] == "lead"]
    assert len(lead_snaps) == 3  # 1 at creation + 2 explicit scoring runs
    for s in lead_snaps:
        assert s["factors"]  # explainable


def test_risk_increases_when_unverified(client, admin_headers):
    from app.tests.conftest import make_ticket_payload
    from app.services.ticket_service import create_ticket
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        p = make_ticket_payload()
        p["original_url"] = None
        p["platform_url"] = None
        t = create_ticket(db, data=p, actor_type="test")
        db.commit()
        assert t.risk_score is not None
        assert t.risk_score >= 25  # unverified + no source URL signals
    finally:
        db.close()
