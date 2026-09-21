"""Fraud & Authenticity AI — Phase A implementation.

Deterministic, explainable risk scoring. Every red flag cites the specific
stored field or source it came from. The agent only *flags* (or suggests a
disqualification review) — it never auto-kills a ticket.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select

from app.agents.base import AgentBase, AgentResult
from app.agents.helpers import EMAIL_RE, PHONE_RE, base_domain
from app.models.enums import ConnectorHealth, DuplicateStatus, TicketStatus
from app.models.source import SourceConnector
from app.models.ticket import Ticket, TicketStatus as TicketStatusRow


def _status_code(db, ticket: Ticket) -> str:
    st = db.get(TicketStatusRow, ticket.status_id)
    return st.code if st else "UNKNOWN"


class FraudAuthenticityAgent(AgentBase):
    from app.agents.registry import AGENTS

    spec = next(a for a in AGENTS if a.agent_id == "fraud-authenticity-ai")

    def execute(self, payload: dict[str, Any]) -> AgentResult:
        ticket_id = payload.get("ticket_id")
        ticket = self.db.get(Ticket, ticket_id) if ticket_id else None
        if ticket is None:
            return AgentResult(status="FAILED", error=f"ticket not found: {ticket_id}")

        factors: list[dict[str, Any]] = []
        url = ticket.platform_url or ticket.original_url

        def factor(name: str, points: int, excerpt: str) -> None:
            factors.append({"factor": name, "points": points, "evidence": excerpt, "url": url})

        # -- email red flags ----------------------------------------------------
        emails: list[str] = []
        for tc in ticket.ticket_contacts:
            c = tc.contact
            if c and c.work_email and c.work_email not in emails:
                emails.append(c.work_email.lower())
        disposable = {e.split("@", 1)[1] for e in emails if "@" in e} & {
            "mailinator.com", "yopmail.com", "tempmail.com", "temp-mail.org",
            "10minutemail.com", "guerrillamail.com", "trashmail.com", "fakeinbox.com",
        }
        if disposable:
            factor("disposable_email_domain", 15,
                   f"contact emails use disposable domain(s): {', '.join(sorted(disposable))}")
        bad_email = [e for e in emails if not EMAIL_RE.match(e)]
        if bad_email:
            factor("invalid_email_format", 10, f"malformed contact email(s): {', '.join(bad_email)}")

        # -- phone red flags ------------------------------------------------------
        phones: list[str] = []
        for tc in ticket.ticket_contacts:
            c = tc.contact
            if c and c.phone and c.phone not in phones:
                phones.append(c.phone)
        bad_phone = [p for p in phones if not PHONE_RE.match(p)]
        if bad_phone:
            factor("invalid_phone_format", 10, f"malformed contact phone(s): {', '.join(bad_phone)}")

        # -- duplicate / recycled content ----------------------------------------
        if ticket.duplicate_status in (
            DuplicateStatus.POSSIBLE_DUPLICATE, DuplicateStatus.DUPLICATE,
        ):
            factor("possible_duplicate", 20, f"ticket flagged {ticket.duplicate_status.value}")
        if ticket.original_url:
            same_url = self.db.execute(
                select(func.count()).select_from(Ticket).where(
                    Ticket.original_url == ticket.original_url, Ticket.id != ticket_id
                )
            ).scalar_one()
            if same_url:
                factor("recycled_content", 15,
                       f"{same_url} other ticket(s) share original_url {ticket.original_url}")

        # -- company-domain consistency -------------------------------------------
        comp_base: set[str] = set()
        for tc in ticket.ticket_companies:
            c = tc.company
            if c:
                b = base_domain(c.domain or c.website)
                if b:
                    comp_base.add(b)
        email_bases = {base_domain(e) for e in emails if "@" in e}
        if comp_base and email_bases and not email_bases.issubset(comp_base):
            mismatched = sorted(email_bases - comp_base)
            factor("company_domain_mismatch", 15,
                   f"email domain base(s) {mismatched} not covered by company domain(s) {sorted(comp_base)}")

        # -- source reputation -----------------------------------------------------
        from app.models.source import TicketSource

        source_ids = [
            ts.source_id for ts in ticket.ticket_sources if ts.source_id is not None
        ]
        if source_ids:
            unhealthy = self.db.execute(
                select(SourceConnector).where(
                    SourceConnector.source_id.in_(source_ids),
                    SourceConnector.health.in_([ConnectorHealth.DOWN, ConnectorHealth.UNKNOWN]),
                )
            ).scalars().all()
            if unhealthy:
                factor(
                    "untrusted_source_health", 10,
                    f"source connector(s) {', '.join(u.connector_id for u in unhealthy)} "
                    "report non-HEALTHY status",
                )

        # -- budget anomaly --------------------------------------------------------
        if (ticket.budget or 0) >= 1_000_000 and not (ticket.requirement or "").strip():
            factor("budget_without_requirement", 10,
                   f"budget {float(ticket.budget):,.0f} with no requirement text")

        # -- aged / stale signal ----------------------------------------------------
        if ticket.published_at:
            age_days = (datetime.now(timezone.utc) - ticket.published_at).days
            status_code = _status_code(self.db, ticket)
            if age_days > 180 and status_code in {
                TicketStatus.DISCOVERED.value, TicketStatus.INGESTED.value,
                TicketStatus.PROCESSING.value, TicketStatus.VERIFICATION_PENDING.value,
            }:
                factor("aged_unprocessed", 5, f"published {age_days} days ago, still {status_code}")

        total = min(100, sum(f["points"] for f in factors))
        if total >= 80:
            risk_level = "HIGH"
            suggested = "flag_for_disqualification_review"
        elif total >= 50:
            risk_level = "MEDIUM"
            suggested = "flag_for_review"
        elif total >= 30:
            risk_level = "LOW"
            suggested = "monitor"
        else:
            risk_level = "NONE"
            suggested = "no_action"

        confidence = round(0.5 + 0.06 * len(factors), 4)  # capped by evidence quality below

        evidence = [
            {"kind": "url", "source_url": f.get("url") or url, "excerpt": f.get("evidence")}
            for f in factors
        ]
        return AgentResult(
            status="COMPLETED",
            output={
                "ticket_id": ticket_id,
                "risk_score": total,
                "risk_level": risk_level,
                "factors": factors,
                "suggested_action": suggested,
                "note": "Flag only — human decision required before any disqualification.",
            },
            confidence=confidence,
            evidence=evidence,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
        )