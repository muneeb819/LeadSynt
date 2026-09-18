"""Ticket CRUD, provenance, pagination, filtering, sorting, validation."""


def test_create_ticket_full_pipeline(client, create_ticket, db_session):
    t = create_ticket()
    assert t["reference"].startswith("TS-")
    assert t["status"] == "INGESTED"
    # Provenance captured
    assert t["original_url"] == "https://devmarket.example.com/listings/t-1"
    assert t["platform"] == "dev-marketplace"
    # Contact + company attached
    assert len(t["contacts"]) == 1
    assert t["contacts"][0]["work_email"] == "john.buyer@acme-fab.example.com"
    assert t["companies"][0]["domain"] == "acme-fab.example.com"
    # Initial scoring applied
    assert t["lead_score"] is not None and 0 <= t["lead_score"] <= 100
    assert t["duplicate_status"] == "UNIQUE"
    # Audit row
    from app.models.ops import AuditLog

    logs = db_session.query(AuditLog).filter(
        AuditLog.action == "ticket.created", AuditLog.resource_id == t["id"]
    ).all()
    assert len(logs) == 1


def test_ticket_reference_unique_and_sequential(client, create_ticket):
    a = create_ticket(product="Alpha")
    b = create_ticket(product="Beta")
    assert a["reference"] != b["reference"]
    prefix = a["reference"][:8]
    assert b["reference"].startswith(prefix)


def test_list_filters_sort_pagination(client, operator_headers, create_ticket):
    create_ticket(market_sector="Energy", product="Turbines")
    create_ticket(market_sector="Retail", product="POS")
    r = client.get("/api/v1/tickets?market_sector=Energy", headers=operator_headers)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["pagination"]["total"] == 1
    assert data["items"][0]["market_sector"] == "Energy"

    # search
    r = client.get("/api/v1/tickets?q=POS", headers=operator_headers)
    assert r.json()["data"]["pagination"]["total"] == 1

    # pagination
    r = client.get("/api/v1/tickets?page=1&page_size=1", headers=operator_headers)
    assert r.json()["data"]["pagination"]["page_size"] == 1
    assert r.json()["data"]["pagination"]["total"] == 2
    assert len(r.json()["data"]["items"]) == 1


def test_list_requires_auth(client):
    r = client.get("/api/v1/tickets")
    assert r.status_code == 401


def test_validation_error_on_bad_intent(client, operator_headers):
    from app.tests.conftest import make_ticket_payload

    r = client.post("/api/v1/tickets",
                    json=make_ticket_payload(intent_level="SUPER_HIGH"),
                    headers=operator_headers)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


def test_detail_404(client, admin_headers):
    r = client.get("/api/v1/tickets/does-not-exist", headers=admin_headers)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_update_ticket_audited(client, admin_headers, create_ticket, db_session):
    t = create_ticket()
    r = client.patch(f"/api/v1/tickets/{t['id']}", json={"urgency": "NOW", "notes": "hot"},
                     headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["data"]["urgency"] == "NOW"
    from app.models.ops import AuditLog

    logs = db_session.query(AuditLog).filter(
        AuditLog.action == "ticket.updated", AuditLog.resource_id == t["id"]
    ).all()
    assert logs and logs[0].before.get("urgency") == "WEEK"


def test_archive_requires_permission(client, viewer_headers, create_ticket):
    t = create_ticket()
    r = client.post(f"/api/v1/tickets/{t['id']}/archive", headers=viewer_headers)
    assert r.status_code == 403
