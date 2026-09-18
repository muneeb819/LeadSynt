"""Ticket status machine tests — the controlled state graph."""

from app.core.exceptions import StatusTransitionError
from app.models.enums import TicketStatus
from app.services.ticket_status_machine import (
    ALLOWED_TRANSITIONS, allowed_from, assert_transition, can_transition,
)


def test_valid_chain_through_machine():
    chain = [
        TicketStatus.DISCOVERED, TicketStatus.INGESTED, TicketStatus.PROCESSING,
        TicketStatus.VERIFICATION_PENDING, TicketStatus.VERIFIED, TicketStatus.QUALIFIED,
        TicketStatus.OUTREACH_READY, TicketStatus.OUTREACH_ACTIVE, TicketStatus.REPLIED,
        TicketStatus.NEGOTIATION, TicketStatus.PROPOSAL_SENT, TicketStatus.WON,
    ]
    for a, b in zip(chain, chain[1:]):
        assert can_transition(a, b), f"{a} -> {b} should be allowed"


def test_illegal_transitions_rejected():
    # jump straight to WON from INGESTED
    assert not can_transition(TicketStatus.INGESTED, TicketStatus.WON)
    # terminal states only allow ARCHIVED
    assert not can_transition(TicketStatus.WON, TicketStatus.ARCHIVED) is False
    assert can_transition(TicketStatus.WON, TicketStatus.ARCHIVED)
    assert not can_transition(TicketStatus.WON, TicketStatus.NEGOTIATION)
    # ARCHIVED is fully terminal
    assert allowed_from(TicketStatus.ARCHIVED) == set()


def test_assert_transition_raises_with_allowed_list():
    try:
        assert_transition(TicketStatus.INGESTED, TicketStatus.WON)
        raise AssertionError("expected StatusTransitionError")
    except StatusTransitionError as e:
        assert "INGESTED" in str(e)
        assert "WON" in str(e)
        assert "WON" not in e.details["allowed"]


def test_api_illegal_transition_returns_409(client, operator_headers, create_ticket):
    t = create_ticket()
    r = client.post(f"/api/v1/tickets/{t['id']}/status",
                    json={"status": "WON"}, headers=operator_headers)
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "invalid_status_transition"
    assert "WON" not in r.json()["error"]["details"]["allowed"]


def test_api_same_status_returns_400(client, operator_headers, create_ticket):
    t = create_ticket()
    r = client.post(f"/api/v1/tickets/{t['id']}/status",
                    json={"status": "INGESTED"}, headers=operator_headers)
    assert r.status_code == 400


def test_api_unknown_status_returns_400(client, operator_headers, create_ticket):
    t = create_ticket()
    r = client.post(f"/api/v1/tickets/{t['id']}/status",
                    json={"status": "FLYING"}, headers=operator_headers)
    assert r.status_code == 400


def test_full_api_walk(client, admin_headers, create_ticket):
    t = create_ticket()
    steps = ["PROCESSING", "VERIFICATION_PENDING", "VERIFIED", "QUALIFIED",
             "OUTREACH_READY", "OUTREACH_ACTIVE", "REPLIED", "AWAITING_HUMAN",
             "MEETING_BOOKED", "NEGOTIATION", "PROPOSAL_SENT", "WON"]
    for step in steps:
        r = client.post(f"/api/v1/tickets/{t['id']}/status",
                        json={"status": step, "reason": "test walk"},
                        headers=admin_headers)
        assert r.status_code == 200, f"{step}: {r.text}"
        assert r.json()["data"]["status"] == step
