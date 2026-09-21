"""Verification AI — Phase A implementation (evidence-backed orchestration).

Runs the deterministic verification engines (email syntax + disposable-domain
blocklist, E.164-style phone format, company domain presence) through the
sanctioned verification service, which stores immutable history. Provider
checks (MX/line-type/cross-reference) remain UNKNOWN when no provider is
configured — the agent never guesses.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentBase, AgentResult
from app.models.enums import VerificationResult
from app.models.ticket import Ticket
from app.services import verification_service as vs

AGENT_NAME = "verification-ai"


class VerificationAgent(AgentBase):
    from app.agents.registry import AGENTS

    spec = next(a for a in AGENTS if a.agent_id == AGENT_NAME)

    def _entity_refs(self, ticket: Ticket) -> dict[str, list[str]]:
        refs: dict[str, list[str]] = {"EMAIL": [], "PHONE": [], "COMPANY": []}
        for tc in ticket.ticket_contacts:
            contact = tc.contact
            if contact and contact.work_email and contact.work_email not in refs["EMAIL"]:
                refs["EMAIL"].append(contact.work_email)
            if contact and contact.phone and contact.phone not in refs["PHONE"]:
                refs["PHONE"].append(contact.phone)
        for tcomp in ticket.ticket_companies:
            company = tcomp.company
            if company and company.id not in refs["COMPANY"]:
                refs["COMPANY"].append(company.id)
        return refs

    def execute(self, payload: dict[str, Any]) -> AgentResult:
        ticket_id = payload.get("ticket_id")
        ticket = self.db.get(Ticket, ticket_id) if ticket_id else None
        if ticket is None:
            return AgentResult(status="FAILED", error=f"ticket not found: {ticket_id}")
        requested = [k.upper() for k in (payload.get("kinds") or ["EMAIL", "PHONE", "COMPANY"])]
        refs = self._entity_refs(ticket)

        results: list[dict] = []
        evidence: list[dict] = []
        for kind in requested:
            for ref in refs.get(kind, []):
                if kind == "EMAIL":
                    rec = vs.verify_email_address(
                        self.db, email=ref, ticket_id=ticket_id, verified_by=AGENT_NAME,
                    )
                elif kind == "PHONE":
                    rec = vs.verify_phone_number(
                        self.db, phone=ref, ticket_id=ticket_id, verified_by=AGENT_NAME,
                    )
                elif kind == "COMPANY":
                    rec = vs.verify_company(
                        self.db, company_id=ref, ticket_id=ticket_id, verified_by=AGENT_NAME,
                    )
                else:
                    continue
                result = rec.result.value if hasattr(rec.result, "value") else str(rec.result)
                results.append({
                    "kind": kind,
                    "entity_ref": ref,
                    "result": result,
                    "confidence": float(rec.confidence or 0),
                    "notes": rec.notes,
                    "evidence": rec.evidence,
                    "record_id": rec.id,
                })
                evidence.append({
                    "kind": "record",
                    "source_url": ticket.original_url,
                    "excerpt": f"verification record {rec.id}: {kind} {ref} = {result} "
                               f"(conf {float(rec.confidence or 0):.2f})",
                })

        if not results:
            return AgentResult(
                status="COMPLETED",
                output={"results": [], "overall": "NO_DATA",
                        "note": "no verifiable entities found on ticket"},
                confidence=0.0,
                evidence=[],
            )

        verified = sum(1 for r in results if r["result"] == VerificationResult.VERIFIED.value)
        failed = sum(1 for r in results if r["result"] == VerificationResult.FAILED.value)
        confidence = round(sum(r["confidence"] for r in results) / len(results), 4)
        overall = (
            "VERIFIED" if verified and not failed else
            "FAILED" if failed and not verified else
            "PARTIAL" if verified and failed else
            "UNKNOWN"
        )
        return AgentResult(
            status="COMPLETED",
            output={
                "ticket_id": ticket_id,
                "results": results,
                "overall": overall,
                "summary": f"{verified} verified, {failed} failed of {len(results)} checks",
            },
            confidence=confidence,
            evidence=evidence,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
        )