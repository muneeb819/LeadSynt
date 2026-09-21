"""Extraction AI — Phase A implementation.

Baseline is a conservative deterministic engine over stored ticket/source
fields and raw source text; each extracted field carries provenance (exact
source span or stored record + URL). When an LLM provider is configured the
agent asks the model to extract the same schema, falling back to the
deterministic engine on any LLM failure. Missing fields are UNKNOWN — never
guessed.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentBase, AgentResult
from app.agents.helpers import extract_budget, extract_dates, extract_emails, extract_phones
from app.ai.llm import CostLimitExceededError, get_llm_client, parse_json_object
from app.models.source import SourceRecord
from app.models.ticket import Ticket

REQUESTED_FIELDS = ("emails", "phones", "budget", "timeline", "product", "service", "location")


class ExtractionAgent(AgentBase):
    from app.agents.registry import AGENTS

    spec = next(a for a in AGENTS if a.agent_id == "extraction-ai")

    # ------------------------------------------------------------------ helpers
    def _ticket_text(self, ticket: Ticket) -> str:
        return " ".join(
            part for part in (ticket.requirement or "", ticket.pain_point or "") if part
        )

    def _collect_contact_values(self, ticket: Ticket) -> tuple[list[str], list[str]]:
        emails: list[str] = []
        phones: list[str] = []
        for tc in ticket.ticket_contacts:
            contact = tc.contact
            if contact:
                if contact.work_email and contact.work_email not in emails:
                    emails.append(contact.work_email)
                if contact.phone and contact.phone not in phones:
                    phones.append(contact.phone)
        return emails, phones

    def _record_text(self, record: SourceRecord) -> str:
        parts: list[str] = []

        def _walk(node: Any) -> None:
            if isinstance(node, str):
                parts.append(node)
            elif isinstance(node, dict):
                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)

        _walk(record.payload)
        return " ".join(parts)

    # ------------------------------------------------------------ deterministic
    def _deterministic(self, ticket: Ticket | None, raw_text: str, url: str | None) -> tuple[dict, list[str]]:
        fields: dict[str, Any] = {}
        provenance: dict[str, list[dict]] = {}

        def add(name: str, value: Any, source: str, span: str | None = None) -> None:
            fields[name] = value
            provenance.setdefault(name, []).append(
                {"source": source, "span": span, "url": url}
            )

        # -- stored structured fields (strongest provenance) -----------------
        if ticket is not None:
            for field_name, field_value in (
                ("product", ticket.product), ("service", ticket.service),
                ("location", ticket.location),
            ):
                if field_value:
                    add(field_name, field_value, "stored_ticket_field",
                        span=f"ticket.{field_name}")
            if ticket.budget is not None:
                add("budget", float(ticket.budget), "stored_ticket_field", span="ticket.budget")
                add("budget_currency", ticket.currency or "UNKNOWN", "stored_ticket_field",
                    span="ticket.currency")

        # -- pattern extraction over raw text ---------------------------------
        emails = extract_emails(raw_text)
        phones = extract_phones(raw_text)
        if ticket is not None:
            stored_emails, stored_phones = self._collect_contact_values(ticket)
            for e in stored_emails:
                if e not in emails:
                    emails.append(e)
                    provenance.setdefault("emails", []).append(
                        {"source": "stored_contact", "span": "contact.work_email", "url": url})
            for p in stored_phones:
                if p not in phones:
                    phones.append(p)
                    provenance.setdefault("phones", []).append(
                        {"source": "stored_contact", "span": "contact.phone", "url": url})
        if emails:
            fields.setdefault("emails", emails)
            provenance.setdefault("emails", []).append(
                {"source": "source_text", "span": "email pattern", "url": url})
        if phones:
            fields.setdefault("phones", phones)
            provenance.setdefault("phones", []).append(
                {"source": "source_text", "span": "phone pattern", "url": url})

        if "budget" not in fields:
            budget_hits = extract_budget(raw_text)
            if budget_hits:
                add("budget", budget_hits[0], "source_text", span="budget pattern")

        if "timeline" not in fields:
            dates = extract_dates(raw_text)
            if dates:
                add("timeline", dates, "source_text", span="date/quarter pattern")

        unknowns = [name for name in REQUESTED_FIELDS if name not in fields]
        return {"fields": fields, "provenance": provenance, "unknowns": unknowns}, unknowns

    # ---------------------------------------------------------------- execution
    def execute(self, payload: dict[str, Any]) -> AgentResult:
        source_record_id = payload.get("source_record_id")
        ticket_id = payload.get("ticket_id")
        if not source_record_id and not ticket_id:
            return AgentResult(status="FAILED", error="payload requires ticket_id or source_record_id")

        ticket: Ticket | None = None
        record: SourceRecord | None = None
        if ticket_id:
            ticket = self.db.get(Ticket, ticket_id)
            if ticket is None:
                return AgentResult(status="FAILED", error=f"ticket not found: {ticket_id}")
        if source_record_id:
            record = self.db.get(SourceRecord, source_record_id)
            if record is None:
                return AgentResult(status="FAILED", error=f"source record not found: {source_record_id}")

        raw_text = (self._record_text(record) if record else "") or (
            self._ticket_text(ticket) if ticket else ""
        )
        url = (record.url if record else None) or (
            ticket.platform_url or ticket.original_url if ticket else None
        ) or None

        evidence: list[dict] = []
        tokens_in = tokens_out = 0
        cost_usd = 0.0

        llm = None
        try:
            llm = get_llm_client(self.db)
        except Exception:  # noqa: BLE001 — never let client setup fail a run
            llm = None

        if llm is not None:
            try:
                from app.core.config import get_settings

                s = get_settings()
                prompt = (
                    "Extract structured fields from this business signal. "
                    "Use the source text ONLY. Never invent values: a field you "
                    "cannot extract must be omitted. Respond with a single JSON "
                    "object: {\"fields\": {\"emails\": [...], \"phones\": [...], "
                    "\"budget\": <number|omit>, \"budget_currency\": <str|omit>, "
                    "\"timeline\": [...], \"product\": <str|omit>, \"service\": "
                    "<str|omit>, \"location\": <str|omit>}}"
                    f"\n\nSource text:\n{raw_text[:6000]}"
                )
                resp = llm.chat(
                    [
                        {"role": "system", "content": self.spec.system_instructions},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=int(s.ai_max_tokens_per_run),
                    max_cost_usd=float(s.ai_max_cost_per_run_usd),
                )
                tokens_in, tokens_out, cost_usd = (
                    resp["tokens_in"], resp["tokens_out"], resp["cost_usd"],
                )
                parsed = parse_json_object(resp["content"])
                fields = parsed.get("fields") or {}
                present = {k: v for k, v in fields.items() if v not in (None, "", [], {})}
                if "budget" in present and "budget_currency" not in present:
                    present["budget_currency"] = "UNKNOWN"
                extracted_names = [
                    n for n in REQUESTED_FIELDS
                    if n in present or (n == "budget_currency" and "budget" in present)
                ]
                unknowns = [n for n in REQUESTED_FIELDS if n not in present]
                prov = [
                    {"source": f"llm:{llm.model_id}", "span": "model extraction", "url": url}
                    for _ in extracted_names
                ]
                evidence = [{"kind": "url", "source_url": url or "", "excerpt": raw_text[:160]}]
                out = {
                    "fields": present,
                    "provenance": {n: prov for n in extracted_names},
                    "unknowns": unknowns,
                    "engine": "llm",
                }
            except CostLimitExceededError as exc:
                return AgentResult(status="FAILED", error=str(exc))
            except Exception:  # noqa: BLE001 — deterministic fallback
                out, unknowns = self._deterministic(ticket, raw_text, url)
                out["engine"] = "deterministic"
        else:
            out, unknowns = self._deterministic(ticket, raw_text, url)
            out["engine"] = "deterministic"

        extracted = [n for n in REQUESTED_FIELDS if n in out.get("fields", {})]
        confidence = round((0.6 + 0.4 * (len(extracted) / len(REQUESTED_FIELDS))), 4) \
            if extracted else 0.2
        if not evidence:
            evidence = [{"kind": "url", "source_url": url or "", "excerpt": "ticket/record"}]

        return AgentResult(
            status="COMPLETED",
            output=out,
            confidence=confidence,
            evidence=evidence,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
        )