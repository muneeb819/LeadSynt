"""Suppression (privacy guardrail) tests: outreach must check suppression."""

import pytest

from app.core.exceptions import SuppressedContactError
from app.models.contact import Contact
from app.services.suppression_service import (
    add_suppression, check_outreach_allowed, is_suppressed,
)


def test_outreach_blocked_for_suppressed_contact(db_session):
    c = Contact(full_name="Opted Out", work_email="out@example.com")
    db_session.add(c)
    db_session.flush()
    assert is_suppressed(db_session, email="out@example.com") is False
    check_outreach_allowed(db_session, c)  # should pass before suppression

    add_suppression(db_session, scope="email", value="out@example.com",
                    contact_id=c.id, reason="opt_out", source="test")
    assert is_suppressed(db_session, email="out@example.com") is True
    with pytest.raises(SuppressedContactError):
        check_outreach_allowed(db_session, c)


def test_contact_suppress_endpoint(client, operator_headers, create_ticket, db_session):
    t = create_ticket()
    contact_id = t["contacts"][0]["id"]
    r = client.post(f"/api/v1/contacts/{contact_id}/suppress",
                    params={"reason": "opt_out"}, headers=operator_headers)
    assert r.status_code == 201, r.text
    from app.models.ops import SuppressionRecord

    rows = db_session.query(SuppressionRecord).filter(
        SuppressionRecord.value == "john.buyer@acme-fab.example.com"
    ).all()
    assert len(rows) == 1


def test_expired_suppression_does_not_block(db_session):
    from datetime import datetime, timedelta, timezone

    c = Contact(full_name="Temporary Block", work_email="temp@example.com")
    db_session.add(c)
    db_session.flush()
    add_suppression(db_session, scope="email", value="temp@example.com",
                    contact_id=c.id, reason="temp", source="test",
                    expires_at=datetime.now(timezone.utc) - timedelta(days=1))
    assert is_suppressed(db_session, email="temp@example.com") is False
