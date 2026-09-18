"""Ticket status machine — the controlled state graph.

Arbitrary status changes are NOT allowed. Every transition is validated
against ``ALLOWED_TRANSITIONS``; violations raise
``StatusTransitionError`` (HTTP 409) and are never silently applied.
"""

from __future__ import annotations

from app.core.exceptions import StatusTransitionError
from app.models.enums import TicketStatus

T = TicketStatus

TERMINAL_STATUSES: set[TicketStatus] = {
    T.WON, T.LOST, T.DISQUALIFIED, T.DUPLICATE, T.EXPIRED, T.ARCHIVED,
}

ALLOWED_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    T.DISCOVERED: {T.INGESTED, T.EXPIRED, T.ARCHIVED},
    T.INGESTED: {T.PROCESSING, T.REVIEW_REQUIRED, T.EXPIRED, T.ARCHIVED},
    T.PROCESSING: {T.REVIEW_REQUIRED, T.VERIFICATION_PENDING, T.QUALIFIED, T.DISQUALIFIED, T.EXPIRED, T.ARCHIVED},
    T.REVIEW_REQUIRED: {T.PROCESSING, T.VERIFICATION_PENDING, T.QUALIFIED, T.DISQUALIFIED, T.ARCHIVED},
    T.VERIFICATION_PENDING: {T.VERIFIED, T.QUALIFIED, T.DISQUALIFIED, T.EXPIRED},
    T.VERIFIED: {T.QUALIFIED, T.OUTREACH_READY, T.DISQUALIFIED, T.DUPLICATE, T.EXPIRED, T.ARCHIVED},
    T.QUALIFIED: {T.OUTREACH_READY, T.DISQUALIFIED, T.EXPIRED, T.ARCHIVED},
    T.OUTREACH_READY: {T.OUTREACH_ACTIVE, T.DISQUALIFIED, T.EXPIRED, T.ARCHIVED},
    T.OUTREACH_ACTIVE: {
        T.REPLIED, T.HOT_LEAD, T.AWAITING_HUMAN, T.NEGOTIATION,
        T.DISQUALIFIED, T.LOST, T.EXPIRED, T.ARCHIVED,
    },
    T.REPLIED: {
        T.HOT_LEAD, T.AWAITING_HUMAN, T.NEGOTIATION, T.MEETING_BOOKED,
        T.DISQUALIFIED, T.LOST, T.ARCHIVED,
    },
    T.HOT_LEAD: {
        T.AWAITING_HUMAN, T.MEETING_BOOKED, T.NEGOTIATION,
        T.DISQUALIFIED, T.LOST, T.ARCHIVED,
    },
    T.AWAITING_HUMAN: {
        T.MEETING_BOOKED, T.NEGOTIATION, T.REPLIED, T.OUTREACH_ACTIVE,
        T.DISQUALIFIED, T.LOST, T.ARCHIVED,
    },
    T.MEETING_BOOKED: {T.NEGOTIATION, T.PROPOSAL_SENT, T.LOST, T.DISQUALIFIED, T.ARCHIVED},
    T.NEGOTIATION: {T.PROPOSAL_SENT, T.WON, T.LOST, T.DISQUALIFIED, T.ARCHIVED},
    T.PROPOSAL_SENT: {T.WON, T.LOST, T.NEGOTIATION, T.DISQUALIFIED, T.ARCHIVED},
    T.WON: {T.ARCHIVED},
    T.LOST: {T.ARCHIVED},
    T.DISQUALIFIED: {T.ARCHIVED},
    T.DUPLICATE: {T.ARCHIVED},
    T.EXPIRED: {T.ARCHIVED},
    T.ARCHIVED: set(),
}


def allowed_from(status: TicketStatus) -> set[TicketStatus]:
    return ALLOWED_TRANSITIONS.get(status, set())


def can_transition(from_status: TicketStatus, to_status: TicketStatus) -> bool:
    if from_status == to_status:
        return False
    return to_status in allowed_from(from_status)


def assert_transition(from_status: TicketStatus, to_status: TicketStatus) -> None:
    if not can_transition(from_status, to_status):
        allowed = sorted(s.value for s in allowed_from(from_status))
        raise StatusTransitionError(
            f"Illegal status transition {from_status.value} -> {to_status.value}. "
            f"Allowed from {from_status.value}: {allowed}",
            details={"from": from_status.value, "to": to_status.value, "allowed": allowed},
        )
