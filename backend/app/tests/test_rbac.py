"""RBAC tests: role boundaries enforced on real endpoints."""


def test_viewer_cannot_create_ticket(client, viewer_headers):
    r = client.post("/api/v1/tickets", json={"type_code": "GENERAL", "product": "x"},
                    headers=viewer_headers)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "forbidden"


def test_operator_can_create_ticket(client, operator_headers, create_ticket):
    t = create_ticket()
    assert t["status"] == "INGESTED"


def test_viewer_can_read_tickets(client, viewer_headers, create_ticket):
    create_ticket()
    r = client.get("/api/v1/tickets", headers=viewer_headers)
    assert r.status_code == 200
    assert r.json()["data"]["pagination"]["total"] >= 1


def test_non_admin_cannot_create_users(client, operator_headers):
    r = client.post("/api/v1/users", json={
        "email": "ghost@example.com", "full_name": "Ghost",
        "password": "Strong-Password-1", "role": "viewer",
    }, headers=operator_headers)
    assert r.status_code == 403


def test_admin_can_create_users(client, admin_headers):
    r = client.post("/api/v1/users", json={
        "email": "staff@example.com", "full_name": "Staff User",
        "password": "Strong-Password-1", "role": "operator",
    }, headers=admin_headers)
    assert r.status_code == 201, r.text
    assert r.json()["data"]["roles"] == ["operator"]


def test_non_admin_cannot_read_audit(client, operator_headers):
    r = client.get("/api/v1/admin/audit", headers=operator_headers)
    assert r.status_code == 403


def test_admin_can_read_audit(client, admin_headers):
    r = client.get("/api/v1/admin/audit", headers=admin_headers)
    assert r.status_code == 200


def test_qa_run_requires_permission(client, operator_headers):
    r = client.post("/api/v1/qa/sweep", headers=operator_headers)
    assert r.status_code == 403
