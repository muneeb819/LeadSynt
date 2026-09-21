"""Enrichment AI — Phase A implementation (licensed/permitted data only).

Enriches tickets/contacts/companies from *configured* providers and from
computed consistency over stored fields. When no enrichment provider is
configured the agent returns only what is already known with provenance, and
reports the rest as UNKNOWN — it never fabricates enrichment values.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentBase, AgentResult
from app.agents.helpers import base_domain
from app.models.company import Company
from app.models.ticket import Ticket

ENRICHED_FIELDS = (
    "official_website", "domain", "industry", "size_band", "country",
    "employee_count", "email_domain_match", "verified_company",
)


class EnrichmentAgent(AgentBase):
    from app.agents.registry import AGENTS

    spec = next(a for a in AGENTS if a.agent_id == "enrichment-ai")

    def execute(self, payload: dict[str, Any]) -> AgentResult:
        ticket_id = payload.get("ticket_id")
        ticket = self.db.get(Ticket, ticket_id) if ticket_id else None
        if ticket is None:
            return AgentResult(status="FAILED", error=f"ticket not found: {ticket_id}")

        company: Company | None = None
        for tc in ticket.ticket_companies:
            if company is None:
                company = tc.company
            # prefer the PRIMARY company
            if tc.role.value == "PRIMARY":
                company = tc.company
                break

        # Enrichment data source. Licensed-dataset providers are not wired in
        # this phase, so the agent stays read-only over stored/computed data
        # and reports unknowns — never fabricated values.
        provider_label = "none"

        fields: dict[str, Any] = {}
        provenance: dict[str, list[dict]] = {}
        if company is None:
            unknowns = [f for f in ENRICHED_FIELDS if f != "email_domain_match"]
            return AgentResult(
                status="COMPLETED",
                output={
                    "fields": fields,
                    "provenance": provenance,
                    "unknowns": unknowns,
                    "provider": provider_label,
                },
                confidence=0.0,
                evidence=[],
            )

        def add(name: str, value: Any, source: str, record_id: str) -> None:
            fields[name] = value
            provenance.setdefault(name, []).append(
                {"source": source, "record_id": record_id,
                 "url": ticket.original_url, "span": f"company.{name}"}
            )

        company_url = company.website or (f"https://{company.domain}" if company.domain else None)
        for name in ("official_website", "domain", "industry", "size_band", "country",
                     "employee_count", "verified_company"):
            # official_website maps to the stored authorized website field;
            # unknown/absent fields stay UNKNOWN — never fabricated.
            value = company.website if name == "official_website" else getattr(company, name, None)
            if value not in (None, "", False):
                add(name, value, "stored_company_record", company.id)

        # Computed consistency: contact email domain vs company domain vs
        # official website — real derived evidence, never fabricated.
        email_domains: list[str] = []
        for tc in ticket.ticket_contacts:
            contact = tc.contact
            if contact and contact.work_email and "@" in contact.work_email:
                email_domains.append(contact.work_email.rsplit("@", 1)[1].lower())
        company_base = base_domain(company.domain or company.website)
        match = "UNKNOWN"
        detail: list[str] = []
        if email_domains and company_base:
            match = "MATCH" if all(base_domain(d) == company_base for d in email_domains) else "MISMATCH"
            detail = [f"email host {d} -> {base_domain(d)} vs company {company_base}" for d in email_domains]
        if email_domains and not company_base:
            match = "UNKNOWN"
            detail = ["no company domain to compare against"]
        add("email_domain_match", {"match": match, "detail": detail}, "computed_consistency", company.id)

        unknowns = [f for f in ENRICHED_FIELDS
                    if f not in fields and f != "email_domain_match"]
        extracted = [f for f in ENRICHED_FIELDS if f in fields]
        confidence = round(len(extracted) / len(ENRICHED_FIELDS), 4)
        evidence = [
            {"kind": "record", "source_url": company_url or ticket.original_url,
             "excerpt": f"company {company.legal_name} (id {company.id})"}
        ]
        return AgentResult(
            status="COMPLETED",
            output={
                "fields": fields,
                "provenance": provenance,
                "unknowns": unknowns,
                "provider": provider_label,
            },
            confidence=confidence,
            evidence=evidence,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
        )