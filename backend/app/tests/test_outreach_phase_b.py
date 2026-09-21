"""Phase B — Outreach engine tests.

Covers: template library + deterministic renderer, message lifecycle through
the send-time gatechain (suppression re-check, consent, reply-pause/handover,
daily cap, quiet hours), channel adapters (log transport QUEUED, mock
delivered SENT, misconfigured SMTP FAILED), reply routing hardening
(sender resolution, opt-out auto-suppression, unsupported channel rejection),
explicit human follow-up authorization, the outreach-ai agent, and the API.
All deterministic — no external email, no API keys.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app.agents.outreach import OutreachAgent
from app.models.outreach import (
    FollowUpRule,
    OutreachFollowUpAuthorization,
    OutreachMessage,
    OutreachTemplate,
)
from app.models.ops import AuditLog, ConsentRecord, SuppressionRecord, WebhookEvent
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


def _raise_daily_cap(db_session, cap: int = 10) -> None:
    from app.configuration import set_setting

    set_setting(db_session, "outreach", {
        "max_daily_per_contact": cap,
        "quiet_hours": {"start": "20:00", "end": "09:00"},
        "require_suppression_check": True,
        "quiet_hours_enabled": False,
    })
    db_session.commit()


def _create_message(client, headers, ticket_id: str, **overrides) -> dict:
    payload = {"ticket_id": ticket_id}
    payload.update(overrides)
    r = client.post("/api/v1/outreach/messages", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["data"]


def _audit_actions(db_session, ticket_id: str | None = None) -> set[str]:
    q = db_session.query(AuditLog)
    if ticket_id:
        q = q.filter(AuditLog.resource_id == ticket_id)
    return {a.action for a in q.all()}


# ---------------------------------------------------------------------------
# Seed + renderer
# ---------------------------------------------------------------------------

def test_outreach_seeded_idempotently(db_session):
    from app.outreach.templates import ensure_outreach_seeded

    ensure_outreach_seeded(db_session)
    db_session.commit()
    ensure_outreach_seeded(db_session)  # idempotent
    templates = db_session.query(OutreachTemplate).all()
    rules = db_session.query(FollowUpRule).all()
    assert len(templates) == 3
    assert len(rules) == 2
    assert {t.name for t in templates} == {"email-sequence-1", "email-sequence-2", "email-sequence-3"}
    assert all(r.requires_human_authorization for r in rules)


def test_render_template_fills_context_and_marks_unresolved(db_session):
    from app.outreach.templates import ensure_outreach_seeded, render_template

    ensure_outreach_seeded(db_session)
    db_session.commit()
    # no ticket/contact yet — unresolved vars must render as UNKNOWN, not guess
    template = db_session.query(OutreachTemplate).filter(
        OutreachTemplate.name == "email-sequence-1"
    ).one()
    subject, body, meta = render_template(template, contact=None, company=None, ticket=None)
    assert subject
    assert "UNKNOWN" in subject or "UNKNOWN" in body
    assert "unresolved_vars" in meta
    assert "opt out" in body.lower()  # compliance footer always appended


def test_render_message_draft_falls_back_when_unseeded(db_session):
    from app.outreach.templates import render_message_draft

    subject, body, meta, template = render_message_draft(
        db_session, channel="email", sequence=1, contact=None, company=None, ticket=None
    )
    assert template is None  # nothing seeded in this bare session
    assert subject and body


# ---------------------------------------------------------------------------
# Templates + messages API
# ---------------------------------------------------------------------------

def test_templates_api_permissions(client, operator_headers, viewer_headers, admin_headers):
    r = client.get("/api/v1/outreach/templates", headers=viewer_headers)
    assert r.status_code == 403
    r = client.get("/api/v1/outreach/templates", headers=operator_headers)
    assert r.status_code == 200
    assert len(r.json()["data"]) == 3  # seeded by lifespan
    # creating templates requires outreach:manage (manager/admin)
    body = {"name": "sms-short", "channel": "sms",
            "subject": "Hi {{first_name}}", "body": "Reply STOP to opt out."}
    r = client.post("/api/v1/outreach/templates", json=body, headers=operator_headers)
    assert r.status_code == 403
    r = client.post("/api/v1/outreach/templates", json=body, headers=admin_headers)
    assert r.status_code == 201
    assert r.json()["data"]["channel"] == "sms"


def test_create_message_via_api_draft(client, operator_headers, create_ticket):
    t = create_ticket()
    r = client.post(
        "/api/v1/outreach/messages",
        json={"ticket_id": t["id"], "template_name": "email-sequence-1"},
        headers=operator_headers,
    )
    assert r.status_code == 201, r.text
    m = r.json()["data"]
    assert m["status"] == "DRAFT"
    assert m["template_id"] is not None
    assert m["channel"] == "email"
    assert m["sequence"] == 1
    assert t["reference"] in m["subject"]
    assert "opt out" in m["body"].lower()
    assert m["meta"]["template"] == "email-sequence-1"


def test_create_message_explicit_body_gets_footer(client, operator_headers, create_ticket):
    t = create_ticket()
    m = _create_message(
        client, operator_headers, t["id"],
        subject="Direct note", body="Hello, let's talk.",
    )
    assert m["status"] == "DRAFT"
    assert m["template_id"] is None
    assert m["body"].startswith("Hello, let's talk.")
    assert "opt out" in m["body"].lower()
    assert m["meta"]["footer_appended"] is True


def test_list_messages_filters(client, operator_headers, create_ticket):
    t = create_ticket()
    m = _create_message(client, operator_headers, t["id"], template_name="email-sequence-1")
    r = client.get(f"/api/v1/outreach/messages?ticket_id={t['id']}", headers=operator_headers)
    assert r.status_code == 200
    assert len(r.json()["data"]) == 1
    assert r.json()["data"][0]["id"] == m["id"]


def test_cancel_message(client, operator_headers, create_ticket, db_session):
    t = create_ticket()
    m = _create_message(client, operator_headers, t["id"], template_name="email-sequence-1")
    r = client.post(f"/api/v1/outreach/messages/{m['id']}/cancel", headers=operator_headers)
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "CANCELLED"
    assert "outreach.cancelled" in _audit_actions(db_session)


# ---------------------------------------------------------------------------
# Send-time gatechain
# ---------------------------------------------------------------------------

def test_send_message_log_transport_queues(client, operator_headers, create_ticket, db_session):
    t = create_ticket()
    m = _create_message(client, operator_headers, t["id"], template_name="email-sequence-1")
    r = client.post(f"/api/v1/outreach/messages/{m['id']}/send", headers=operator_headers)
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "QUEUED"
    assert data["delivered"] is False
    detail = client.get(f"/api/v1/outreach/messages/{m['id']}", headers=operator_headers).json()["data"]
    assert detail["status"] == "QUEUED"
    assert detail["transport"] == "log"
    assert "outreach.queued" in _audit_actions(db_session)


def test_send_time_suppression_blocks(client, operator_headers, create_ticket, db_session):
    from app.services.suppression_service import add_suppression

    t = create_ticket()
    add_suppression(db_session, scope="email", value=t["contacts"][0]["work_email"],
                    reason="test opt-out")
    db_session.commit()
    m = _create_message(client, operator_headers, t["id"], template_name="email-sequence-1")
    r = client.post(f"/api/v1/outreach/messages/{m['id']}/send", headers=operator_headers)
    data = r.json()["data"]
    # suppressed at SEND time even though the draft was created earlier
    assert data["status"] == "BLOCKED"
    assert data["block_reason"] == "suppression"
    detail = client.get(f"/api/v1/outreach/messages/{m['id']}", headers=operator_headers).json()["data"]
    assert detail["status"] == "BLOCKED"
    assert "outreach.blocked:suppression" in _audit_actions(db_session)


def test_daily_cap_blocks_second_send(client, operator_headers, create_ticket):
    # lifespan seeds max_daily_per_contact=1
    t = create_ticket()
    m1 = _create_message(client, operator_headers, t["id"], template_name="email-sequence-1")
    r1 = client.post(f"/api/v1/outreach/messages/{m1['id']}/send", headers=operator_headers).json()["data"]
    assert r1["status"] == "QUEUED"
    m2 = _create_message(client, operator_headers, t["id"], template_name="email-sequence-2", sequence=2)
    r2 = client.post(f"/api/v1/outreach/messages/{m2['id']}/send", headers=operator_headers).json()["data"]
    assert r2["status"] == "BLOCKED"
    assert r2["block_reason"] == "daily_cap"


def test_reply_pause_blocks_then_authorize_unlocks(
    client, operator_headers, create_ticket, db_session
):
    _raise_daily_cap(db_session, cap=10)
    t = create_ticket()
    _activate(client, operator_headers, t["id"])

    # initial message sends fine (no reply yet)
    m1 = _create_message(client, operator_headers, t["id"], template_name="email-sequence-1")
    r1 = client.post(f"/api/v1/outreach/messages/{m1['id']}/send", headers=operator_headers).json()["data"]
    assert r1["status"] == "QUEUED"

    # prospect replies -> handover pauses automated outreach
    payload = json.dumps({
        "ticket_id": t["id"], "message": "Thanks — can you send details and a quote?",
        "sender": t["contacts"][0]["work_email"],
    }).encode()
    resp = client.post("/api/v1/webhooks/reply", content=payload,
                       headers=_sign("test-webhook-secret", payload))
    assert resp.status_code == 200
    assert client.get(f"/api/v1/tickets/{t['id']}", headers=operator_headers).json()["data"]["status"] == "HOT_LEAD"
    assert "outreach.automation_paused" in _audit_actions(db_session, t["id"])

    # follow-up is blocked by the reply-pause (handover) rule
    m2 = _create_message(client, operator_headers, t["id"], template_name="email-sequence-2", sequence=2)
    r2 = client.post(f"/api/v1/outreach/messages/{m2['id']}/send", headers=operator_headers).json()["data"]
    assert r2["status"] == "BLOCKED"
    assert r2["block_reason"] == "reply_pause"

    # explicit human authorization unlocks it
    auth = client.post(
        "/api/v1/outreach/follow-ups/authorize",
        json={"ticket_id": t["id"], "max_follow_ups": 3, "notes": "client asked for details"},
        headers=operator_headers,
    )
    assert auth.status_code == 200, auth.text
    assert "outreach.followup.authorized" in _audit_actions(db_session)

    m3 = _create_message(client, operator_headers, t["id"], template_name="email-sequence-2", sequence=2)
    r3 = client.post(f"/api/v1/outreach/messages/{m3['id']}/send", headers=operator_headers).json()["data"]
    assert r3["status"] == "QUEUED"


def test_consent_withdrawn_blocks(client, operator_headers, create_ticket, db_session):
    t = create_ticket()
    db_session.add(ConsentRecord(
        contact_id=t["contacts"][0]["id"], purpose="outreach",
        status="WITHDRAWN", withdrawn_at=datetime.now(timezone.utc),
    ))
    db_session.commit()
    m = _create_message(client, operator_headers, t["id"], template_name="email-sequence-1")
    r = client.post(f"/api/v1/outreach/messages/{m['id']}/send", headers=operator_headers).json()["data"]
    assert r["status"] == "BLOCKED"
    assert r["block_reason"] == "consent"


def test_misconfigured_smtp_fails(client, operator_headers, create_ticket, db_session, monkeypatch):
    from app.core.config import get_settings

    # switch transport to smtp while SMTP host is unset -> honest FAILED
    monkeypatch.setattr(get_settings(), "outreach_email_transport", "smtp")
    t = create_ticket()
    m = _create_message(client, operator_headers, t["id"], template_name="email-sequence-1")
    r = client.post(f"/api/v1/outreach/messages/{m['id']}/send", headers=operator_headers)
    data = r.json()["data"]
    assert data["status"] == "FAILED"
    assert "smtp" in data["error"].lower()
    detail = client.get(f"/api/v1/outreach/messages/{m['id']}", headers=operator_headers).json()["data"]
    assert detail["status"] == "FAILED"
    assert "outreach.failed" in _audit_actions(db_session)


def test_delivered_path_records_conversation(
    client, operator_headers, create_ticket, db_session, monkeypatch
):
    from app.core.database import SessionLocal
    from app.models.conversation import ConversationMessage
    from app.outreach.base import DeliveryResult
    from app.outreach.email import EmailAdapter

    def fake_send(self, *, message, contact, ticket):  # noqa: ANN001
        return DeliveryResult(delivered=True, transport="fake", provider_ref="test-provider-1")

    monkeypatch.setattr(EmailAdapter, "send", fake_send)
    t = create_ticket()
    m = _create_message(client, operator_headers, t["id"], template_name="email-sequence-1")
    r = client.post(f"/api/v1/outreach/messages/{m['id']}/send", headers=operator_headers)
    data = r.json()["data"]
    assert data["status"] == "SENT"
    assert data["provider_ref"] == "test-provider-1"
    detail = client.get(f"/api/v1/outreach/messages/{m['id']}", headers=operator_headers).json()["data"]
    assert detail["status"] == "SENT"
    assert detail["sent_at"] is not None

    db = SessionLocal()
    cm = db.query(ConversationMessage).filter(ConversationMessage.direction == "outgoing").one()
    assert cm.content == detail["body"]
    assert cm.metadata_["provider_ref"] == "test-provider-1"
    actions = {a.action for a in db.query(AuditLog).all()}
    db.close()
    assert "outreach.sent" in actions


def test_run_due_processes_only_due(client, operator_headers, create_ticket):
    t = create_ticket()
    future = (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat()
    fmsg = _create_message(client, operator_headers, t["id"],
                           template_name="email-sequence-1", scheduled_for=future)
    assert fmsg["status"] == "SCHEDULED"
    r = client.post("/api/v1/outreach/messages/run-due", headers=operator_headers).json()["data"]
    assert r["attempted"] == 0

    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    pmsg = _create_message(client, operator_headers, t["id"],
                           template_name="email-sequence-1", scheduled_for=past)
    assert pmsg["status"] == "SCHEDULED"
    r = client.post("/api/v1/outreach/messages/run-due", headers=operator_headers).json()["data"]
    assert r["attempted"] == 1
    assert r["queued"] == 1


def test_quiet_hours_opt_in_blocks(client, operator_headers, create_ticket, db_session):
    from app.configuration import set_setting

    # window of ±30 minutes around the current UTC time — always quiet right now
    now = datetime.now(timezone.utc)
    minutes = now.hour * 60 + now.minute

    def _fmt(m: int) -> str:
        m %= 1440
        return f"{m // 60:02d}:{m % 60:02d}"

    set_setting(db_session, "outreach", {
        "max_daily_per_contact": 20,
        "quiet_hours": {"start": _fmt(minutes - 30), "end": _fmt(minutes + 30)},
        "require_suppression_check": True,
        "quiet_hours_enabled": True,
    })
    db_session.commit()
    t = create_ticket()
    m = _create_message(client, operator_headers, t["id"], template_name="email-sequence-1")
    r = client.post(f"/api/v1/outreach/messages/{m['id']}/send", headers=operator_headers).json()["data"]
    assert r["status"] == "BLOCKED"
    assert r["block_reason"] == "quiet_hours"


# ---------------------------------------------------------------------------
# Reply routing hardening
# ---------------------------------------------------------------------------

def test_reply_routing_sender_resolution_and_opt_out(
    client, operator_headers, create_ticket, db_session
):
    t = create_ticket()
    _activate(client, operator_headers, t["id"])
    sender = t["contacts"][0]["work_email"]

    # reply WITHOUT ticket_id — routed by sender identity
    payload = json.dumps({
        "message": "Please unsubscribe me from all future emails.",
        "sender": sender, "channel": "email",
    }).encode()
    resp = client.post("/api/v1/webhooks/reply", content=payload,
                       headers=_sign("test-webhook-secret", payload))
    assert resp.status_code == 200, resp.text
    assert resp.json()["ticket_id"] == t["id"]

    recs = db_session.query(SuppressionRecord).filter(SuppressionRecord.value == sender).all()
    assert len(recs) == 1
    assert recs[0].reason == "explicit opt-out in reply"
    assert "outreach.opted_out" in _audit_actions(db_session, t["id"])

    detail = client.get(f"/api/v1/tickets/{t['id']}", headers=operator_headers).json()["data"]
    assert detail["status"] == "REPLIED"

    # suppression now blocks any send to this contact
    m = _create_message(client, operator_headers, t["id"], template_name="email-sequence-2", sequence=2)
    r = client.post(f"/api/v1/outreach/messages/{m['id']}/send", headers=operator_headers).json()["data"]
    assert r["status"] == "BLOCKED"
    assert r["block_reason"] == "suppression"


def test_reply_routing_unsupported_channel_rejected(client, create_ticket, db_session):
    t = create_ticket()
    payload = json.dumps({
        "ticket_id": t["id"], "message": "hello", "channel": "whatsapp",
    }).encode()
    resp = client.post("/api/v1/webhooks/reply", content=payload,
                       headers=_sign("test-webhook-secret", payload))
    assert resp.status_code == 400
    ev = db_session.query(WebhookEvent).first()
    assert ev.status == "FAILED"
    assert ev.error is not None
    assert "webhook.rejected:unsupported_channel" in _audit_actions(db_session)


def test_reply_routing_unknown_signature_rejected(client, db_session):
    payload = json.dumps({"message": "hello", "ticket_id": "bogus"}).encode()
    resp = client.post("/api/v1/webhooks/reply", content=payload,
                       headers=_sign("wrong-secret", payload))
    assert resp.status_code == 401
    ev = db_session.query(WebhookEvent).first()
    assert ev.status == "FAILED"
    assert ev.signature_verified is False


def test_reply_routing_unresolvable_404(client, db_session):
    payload = json.dumps({"message": "hello", "channel": "email"}).encode()
    resp = client.post("/api/v1/webhooks/reply", content=payload,
                       headers=_sign("test-webhook-secret", payload))
    assert resp.status_code == 404
    assert db_session.query(WebhookEvent).first().status == "FAILED"


# ---------------------------------------------------------------------------
# Follow-up rules + authorization API
# ---------------------------------------------------------------------------

def test_follow_up_rules_listed(client, operator_headers):
    r = client.get("/api/v1/outreach/follow-ups", headers=operator_headers)
    assert r.status_code == 200
    rules = r.json()["data"]
    assert len(rules) == 2
    assert {x["sequence"] for x in rules} == {2, 3}
    assert all(x["requires_human_authorization"] for x in rules)


def test_followup_authorization_records_and_lists(client, operator_headers, create_ticket):
    t = create_ticket()
    r = client.post(
        "/api/v1/outreach/follow-ups/authorize",
        json={"ticket_id": t["id"], "max_follow_ups": 2, "notes": "ok to follow up"},
        headers=operator_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["ticket_id"] == t["id"]
    assert data["max_follow_ups"] == 2
    lst = client.get(
        f"/api/v1/outreach/follow-ups/authorizations?ticket_id={t['id']}",
        headers=operator_headers,
    ).json()["data"]
    assert len(lst) == 1
    assert lst[0]["notes"] == "ok to follow up"


# ---------------------------------------------------------------------------
# Outreach agent
# ---------------------------------------------------------------------------

def test_outreach_agent_drafts_and_live_suppression_check(db_session, create_ticket):
    from app.outreach.templates import ensure_outreach_seeded
    from app.services.suppression_service import add_suppression

    ensure_outreach_seeded(db_session)
    db_session.commit()
    t = create_ticket()

    agent = OutreachAgent(db_session)
    run = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="outreach")
    db_session.commit()
    assert run.status.value == "COMPLETED"
    out = run.output
    assert out["suppression_ok"] is True
    assert out["template"] == "email-sequence-1"
    assert out["subject"] and out["body"]
    assert "opt out" in out["body"].lower()

    # add a suppression -> the same draft check now reports blocked
    add_suppression(db_session, scope="email", value=t["contacts"][0]["work_email"],
                    reason="test")
    db_session.commit()
    run2 = agent.run(payload={"ticket_id": t["id"]}, ticket_id=t["id"], kind="outreach")
    db_session.commit()
    assert run2.output["suppression_ok"] is False
    assert run2.output["draft_status"] == "BLOCKED_SUPPRESSION"


def test_outreach_agent_runnable_via_api(client, admin_headers, create_ticket):
    t = create_ticket()
    r = client.post(
        "/api/v1/agents/outreach-ai/run",
        json={"ticket_id": t["id"]},
        headers=admin_headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()["data"]
    assert data["status"] == "COMPLETED"
    assert data["output"]["suppression_ok"] is True