"""Verification tests: deterministic checks, history storage, ticket rollup."""


def test_invalid_email_fails(client, operator_headers, create_ticket):
    t = create_ticket()
    r = client.post("/api/v1/verification/email",
                    json={"ticket_id": t["id"], "email": "not-an-email"},
                    headers=operator_headers)
    assert r.status_code == 200
    assert r.json()["data"]["result"] == "FAILED"


def test_disposable_email_fails_and_rollups(client, operator_headers, create_ticket):
    t = create_ticket()
    r = client.post("/api/v1/verification/email",
                    json={"ticket_id": t["id"], "email": "spam@mailinator.com"},
                    headers=operator_headers)
    assert r.status_code == 200
    assert r.json()["data"]["result"] == "FAILED"
    detail = client.get(f"/api/v1/tickets/{t['id']}", headers=operator_headers).json()["data"]
    assert detail["verification_status"] == "FAILED"


def test_valid_email_verifies_and_rollups(client, operator_headers, create_ticket):
    t = create_ticket()
    r = client.post("/api/v1/verification/email",
                    json={"ticket_id": t["id"], "email": "john.buyer@acme-fab.example.com"},
                    headers=operator_headers)
    assert r.json()["data"]["result"] == "VERIFIED"
    detail = client.get(f"/api/v1/tickets/{t['id']}", headers=operator_headers).json()["data"]
    assert detail["verification_status"] == "VERIFIED"
    assert detail["last_verified_at"] is not None
    # history stored, never overwritten
    assert len(detail["verification_history"]) == 1


def test_history_accumulates(client, operator_headers, create_ticket):
    t = create_ticket()
    client.post("/api/v1/verification/email",
                json={"ticket_id": t["id"], "email": "a@mailinator.com"},
                headers=operator_headers)
    client.post("/api/v1/verification/email",
                json={"ticket_id": t["id"], "email": "b@good.example.com"},
                headers=operator_headers)
    r = client.get(f"/api/v1/verification/history/{t['id']}", headers=operator_headers)
    assert r.status_code == 200
    assert len(r.json()["data"]) == 2


def test_phone_verification(client, operator_headers, create_ticket):
    t = create_ticket()
    r = client.post("/api/v1/verification/phone",
                    json={"ticket_id": t["id"], "phone": "+92 21 555 0100"},
                    headers=operator_headers)
    assert r.json()["data"]["result"] == "VERIFIED"
    r2 = client.post("/api/v1/verification/phone",
                     json={"ticket_id": t["id"], "phone": "12"},
                     headers=operator_headers)
    assert r2.json()["data"]["result"] == "FAILED"
