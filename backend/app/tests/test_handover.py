"""CRITICAL reply-handover rule tests (spec §16) — the most important
business rule, plus webhook signature security."""

import json
import time

from app.security import sign_payload


def _sign(secret: str, body: bytes) -> dict:
    sig, ts = sign_payload(secret, body)
    return {
        "X-LeadSynt-Signature": sig,
        "X-LeadSynt-Timestamp": str(ts),
        "X-LeadSynt-Source": "test-inbox",
        "Content-Type": "application/json",
    }


def _activate(client, headers, ticket_id: str) -> None:
    for step in ["PROCESSING", "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED",
                 "OUTREACH_READY", "OUTREACH_ACTIVE"]:
        r = client.post(f"/api/v1/tickets/{ticket_id}/status",
                        json={"status": step}, headers=headers)
        assert r.status_code == 200, f"{step}: {r.text}"


def test_reply_webhook_triggers_full_handover(client, operator_headers, create_ticket, db_session):
    t = create_ticket()
    _activate(client, operator_headers, t["id"])
    # assign owner so notification has a recipient
    client.patch(f"/api/v1/tickets/{t['id']}", json={}, headers=operator_headers)
    from app.core.database import SessionLocal
    from app.models.ticket import Ticket

    db = SessionLocal()
    ticket = db.get(Ticket, t["id"])
    # set owner directly (same user as operator)
    from app.tests.conftest import _make_user
    owner_id = _make_user(db, "owner@example.com", "operator")
    db.commit()
    ticket.owner_id = owner_id
    db.commit()
    db.close()

    payload = json.dumps({
        "ticket_id": t["id"],
        "message": "Hi, we are very interested — can we schedule a call next week? What is your price range?",
        "sender": "john.buyer@acme-fab.example.com",
        "contact_id": t["contacts"][0]["id"],
    }).encode()
    resp = client.post("/api/v1/webhooks/reply", content=payload,
                       headers=_sign("test-webhook-secret", payload))
    assert resp.status_code == 200, resp.text

    # 1. Status changed to HOT_LEAD (positive reply from OUTREACH_ACTIVE)
    detail = client.get(f"/api/v1/tickets/{t['id']}", headers=operator_headers).json()["data"]
    assert detail["status"] == "HOT_LEAD"

    # 2. Verbatim message recorded in conversation
    d = client.get(f"/api/v1/handover/{t['id']}/dossier", headers=operator_headers).json()["data"]
    assert d["automation_paused"] is True
    assert d["handover"] is not None
    assert d["handover"]["incoming_message"].startswith("Hi, we are very interested")
    assert len(d["conversation"]) == 1
    assert d["conversation"][0]["direction"] == "incoming"

    # 3. Owner notified immediately (in-app)
    from app.models.ops import Notification

    db = SessionLocal()
    n = db.query(Notification).filter(
        Notification.user_id == owner_id, Notification.type == "HANDOVER"
    ).first()
    assert n is not None
    assert t["reference"] in n.title
    db.close()

    # 4. Audit trail: handover.created + outreach.automation_paused
    from app.models.ops import AuditLog

    db = SessionLocal()
    actions = {a.action for a in db.query(AuditLog).filter(
        AuditLog.resource_id == t["id"],
        AuditLog.action.in_(["handover.created", "outreach.automation_paused"]),
    ).all()}
    assert actions == {"handover.created", "outreach.automation_paused"}
    db.close()


def test_reply_with_negative_sentiment_goes_to_replied(client, operator_headers, create_ticket):
    t = create_ticket()
    _activate(client, operator_headers, t["id"])
    payload = json.dumps({
        "ticket_id": t["id"],
        "message": "Please stop emailing me, I am not interested.",
        "sender": "john.buyer@acme-fab.example.com",
    }).encode()
    resp = client.post("/api/v1/webhooks/reply", content=payload,
                       headers=_sign("test-webhook-secret", payload))
    assert resp.status_code == 200
    detail = client.get(f"/api/v1/tickets/{t['id']}", headers=operator_headers).json()["data"]
    assert detail["status"] == "REPLIED"
    d = client.get(f"/api/v1/handover/{t['id']}/dossier", headers=operator_headers).json()["data"]
    assert d["handover"]["intent_classification"] == "negative"
    assert "suppression" in d["handover"]["suggested_next_action"].lower()


def test_reply_webhook_rejects_bad_signature(client, operator_headers, create_ticket, db_session):
    t = create_ticket()
    payload = json.dumps({"ticket_id": t["id"], "message": "hello"}).encode()
    resp = client.post("/api/v1/webhooks/reply", content=payload,
                       headers=_sign("WRONG-SECRET", payload))
    assert resp.status_code == 401
    from app.models.ops import WebhookEvent

    ev = db_session.query(WebhookEvent).first()
    assert ev is not None
    assert ev.signature_verified is False
    assert ev.status == "FAILED"


def test_reply_webhook_rejects_stale_timestamp(client, operator_headers, create_ticket):
    t = create_ticket()
    payload = json.dumps({"ticket_id": t["id"], "message": "hello"}).encode()
    sig, ts = sign_payload("test-webhook-secret", payload, int(time.time()) - 9999)
    resp = client.post("/api/v1/webhooks/reply", content=payload, headers={
        "X-LeadSynt-Signature": sig, "X-LeadSynt-Timestamp": str(ts),
        "X-LeadSynt-Source": "test", "Content-Type": "application/json",
    })
    assert resp.status_code == 401


def test_reply_webhook_rejects_tampered_body(client, operator_headers, create_ticket):
    t = create_ticket()
    payload = json.dumps({"ticket_id": t["id"], "message": "original"}).encode()
    headers = _sign("test-webhook-secret", payload)
    tampered = json.dumps({"ticket_id": t["id"], "message": "tampered"}).encode()
    resp = client.post("/api/v1/webhooks/reply", content=tampered, headers=headers)
    assert resp.status_code == 401
