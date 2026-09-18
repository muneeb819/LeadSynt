"""Dashboard/analytics + notifications + settings: real data, real API."""


def test_dashboard_kpis_from_real_data(client, admin_headers, create_ticket, db_session):
    t = create_ticket()
    # advance one ticket to QUALIFIED
    for step in ["PROCESSING", "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED"]:
        client.post(f"/api/v1/tickets/{t['id']}/status", json={"status": step},
                    headers=admin_headers)
    # run REAL email verification so the verification KPI reflects data state
    r = client.post("/api/v1/verification/email",
                    json={"ticket_id": t["id"],
                          "email": t["contacts"][0]["work_email"]},
                    headers=admin_headers)
    assert r.json()["data"]["result"] == "VERIFIED"
    r = client.get("/api/v1/analytics/dashboard", headers=admin_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["kpis"]["qualified_tickets"] >= 1
    assert data["kpis"]["new_tickets_24h"] >= 1
    assert data["kpis"]["verified_tickets"] >= 1
    assert sum(data["pipeline_by_status"].values()) >= 1
    assert "health" in data and "connectors" in data["health"]


def test_notifications_flow(client, admin_headers, create_ticket, db_session):
    t = create_ticket()
    # trigger a handover so a notification is created for the owner
    from app.core.database import SessionLocal
    from app.models.ticket import Ticket
    from app.tests.conftest import _make_user

    db = SessionLocal()
    owner_id = _make_user(db, "owner2@example.com", "operator")
    ticket = db.get(Ticket, t["id"])
    ticket.owner_id = owner_id
    db.commit()
    db.close()

    for step in ["PROCESSING", "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED",
                 "OUTREACH_READY", "OUTREACH_ACTIVE"]:
        client.post(f"/api/v1/tickets/{t['id']}/status", json={"status": step},
                    headers=admin_headers)

    import json
    from app.security import sign_payload

    payload = json.dumps({"ticket_id": t["id"], "message": "interested in a call",
                          "sender": "x@y.example.com"}).encode()
    sig, ts = sign_payload("test-webhook-secret", payload)
    resp = client.post("/api/v1/webhooks/reply", content=payload, headers={
        "X-LeadSynt-Signature": sig, "X-LeadSynt-Timestamp": str(ts),
        "X-LeadSynt-Source": "test", "Content-Type": "application/json",
    })
    assert resp.status_code == 200

    # owner should now have a HANDOVER notification
    from app.models.ops import Notification

    db = SessionLocal()
    n = db.query(Notification).filter(Notification.user_id == owner_id).first()
    assert n is not None and n.type.value == "HANDOVER"
    db.close()


def test_settings_read_and_update(client, admin_headers):
    r = client.get("/api/v1/settings", headers=admin_headers)
    assert r.status_code == 200
    keys = {s["key"] for s in r.json()["data"]}
    assert "scoring" in keys and "outreach" in keys and "retention" in keys

    r2 = client.put("/api/v1/settings/scoring",
                    json={"value": {"qualification_threshold": 75}},
                    headers=admin_headers)
    assert r2.status_code == 200
    assert r2.json()["data"]["value"]["qualification_threshold"] == 75

    r3 = client.get("/api/v1/settings", headers=admin_headers)
    scoring = next(s for s in r3.json()["data"] if s["key"] == "scoring")
    assert scoring["value"]["qualification_threshold"] == 75


def test_leads_endpoint(client, admin_headers, create_ticket):
    t = create_ticket()
    for step in ["PROCESSING", "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED"]:
        client.post(f"/api/v1/tickets/{t['id']}/status", json={"status": step},
                    headers=admin_headers)
    r = client.get("/api/v1/leads", headers=admin_headers)
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert any(i["id"] == t["id"] for i in items)


def test_contacts_and_companies_endpoints(client, admin_headers, create_ticket):
    create_ticket()
    r = client.get("/api/v1/contacts?q=acme", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["data"]["pagination"]["total"] >= 1
    r2 = client.get("/api/v1/companies?q=acme", headers=admin_headers)
    assert r2.status_code == 200
    assert r2.json()["data"]["pagination"]["total"] >= 1


def test_audit_endpoint_filters(client, admin_headers, create_ticket):
    create_ticket()
    r = client.get("/api/v1/admin/audit?action=ticket.created", headers=admin_headers)
    assert r.status_code == 200
    items = r.json()["data"]
    assert len(items) >= 1
    assert all(i["action"] == "ticket.created" for i in items)
    assert items[0]["after"]["reference"].startswith("TS-")
