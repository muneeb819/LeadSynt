"""Concrete Outreach Agent (Phase B): compliant outreach drafting.

The agent READS the ticket and RETURNS a ready-to-schedule draft plus the
result of a LIVE suppression re-check. It NEVER sends anything — sending is
an audited service action gated by the send-time gatechain in the outreach
service (suppression -> consent -> reply-pause -> daily cap -> quiet hours).
Provenance stays exact: the drafted body is a snapshot the operator can
schedule, and every scheduled/sent message is recorded in ``outreach_messages``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.agents.base import AgentBase, AgentResult
from app.agents.registry import AGENTS
from app.models.outreach import FollowUpRule
from app.models.ticket import Ticket
from app.outreach.service import _company_for, _primary_contact
from app.outreach.templates import render_message_draft
from app.services.suppression_service import is_suppressed


class OutreachAgent(AgentBase):
    spec = next(a for a in AGENTS if a.agent_id == "outreach-ai")

    def execute(self, payload: dict[str, Any]) -> AgentResult:
        ticket_id = payload.get("ticket_id")
        ticket = self.db.get(Ticket, ticket_id)
        if ticket is None:
            return AgentResult(status="FAILED", error=f"ticket not found: {ticket_id}")

        channel = str(payload.get("channel", "email") or "email").lower()
        sequence = max(1, int(payload.get("sequence", 1) or 1))

        contact = _primary_contact(self.db, ticket_id)
        company = _company_for(self.db, ticket_id)

        # Live suppression re-check — the compliance gate, computed at draft
        # time (and re-checked again mandatorily at send time).
        suppression_ok = not (
            contact is not None
            and is_suppressed(
                self.db,
                email=contact.work_email,
                phone=contact.phone,
                contact_id=contact.id,
            )
        )

        subject, body, meta, template = render_message_draft(
            self.db,
            channel=channel,
            sequence=sequence,
            contact=contact,
            company=company,
            ticket=ticket,
        )
        _ = meta  # metadata is already snapshotted into the stored message

        follow_up_rule = self.db.execute(
            select(FollowUpRule).where(
                FollowUpRule.channel == channel,
                FollowUpRule.sequence == sequence,
            )
        ).scalars().first()

        return AgentResult(
            status="COMPLETED",
            output={
                "ticket_id": ticket_id,
                "channel": channel,
                "sequence": sequence,
                "template": template.name if template else None,
                "subject": subject,
                "body": body,
                "suppression_ok": suppression_ok,
                "draft_status": "SCHEDULABLE" if suppression_ok else "BLOCKED_SUPPRESSION",
                "suggested_delay_hours": follow_up_rule.delay_hours if follow_up_rule else None,
                "requires_human_authorization": bool(follow_up_rule and follow_up_rule.requires_human_authorization),
            },
            confidence=1.0,  # deterministic draft + live suppression check
            evidence=[
                {"kind": "record", "source_url": ticket.original_url,
                 "excerpt": f"ticket {ticket.reference} suppression_ok={suppression_ok}"},
                {"kind": "template", "excerpt": f"channel={channel} sequence={sequence} template={template.name if template else 'builtin'}"},
            ],
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
        )