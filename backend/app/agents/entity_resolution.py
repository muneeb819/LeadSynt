"""Entity Resolution AI — Phase A implementation.

Resolves companies via the company-domain graph (exact domain, company_domains
rows, registrable base-domain) and normalized-name matching (strict equality +
token Jaccard with an explicit threshold). Merge proposals are produced only
at confidence >= 0.9 and always require human confirmation — the agent never
auto-merges.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import AgentBase, AgentResult
from app.agents.helpers import base_domain, jaccard, name_tokens, normalize_company_name
from app.models.company import Company

MERGE_THRESHOLD = 0.9


class EntityResolutionAgent(AgentBase):
    from app.agents.registry import AGENTS

    spec = next(a for a in AGENTS if a.agent_id == "entity-resolution-ai")

    def _all_companies(self) -> list[Company]:
        from sqlalchemy import select

        return list(self.db.execute(select(Company)).scalars().all())

    def _base_domains(self, company: Company) -> set[str]:
        out = {base_domain(d) for d in (company.domain, company.website)}
        for cd in company.domains:
            out.add(base_domain(cd.domain))
        return {d for d in out if d}

    def execute(self, payload: dict[str, Any]) -> AgentResult:
        entity_kind = (payload.get("entity_kind") or "company").lower()
        entity_ref = payload.get("entity_ref")
        if not entity_ref:
            return AgentResult(status="FAILED", error="payload requires entity_ref")
        if entity_kind not in {"company", "domain"}:
            entity_kind = "company"

        ref = str(entity_ref)
        companies = self._all_companies()
        matches: list[dict[str, Any]] = []
        candidates: list[tuple[Company, float, str, dict]] = []
        source_company: Company | None = None
        for c in companies:
            if c.id == ref:
                source_company = c
                break

        if source_company is not None:
            ref_name = normalize_company_name(source_company.legal_name)
            ref_tokens = name_tokens(source_company.legal_name)
            ref_bases = self._base_domains(source_company)
            for c in companies:
                if c.id == source_company.id:
                    continue
                compared: dict[str, Any] = {}
                conf = 0.0
                kind = ""
                # exact domain overlap
                shared = ref_bases & self._base_domains(c)
                if shared:
                    kind = "exact_domain"
                    conf = 0.98
                    compared["domain"] = sorted(shared)
                if not kind:
                    # normalized-name equality
                    if ref_name and normalize_company_name(c.legal_name) == ref_name:
                        kind = "normalized_name"
                        conf = 0.95
                        compared["legal_name"] = c.legal_name
                if not kind and ref_tokens:
                    sim = jaccard(ref_tokens, name_tokens(c.legal_name))
                    if sim >= 0.75:
                        kind = "token_similarity"
                        conf = round(sim, 4)
                        compared["legal_name_similarity"] = sim
                if kind:
                    candidates.append((c, conf, kind, compared))
        else:
            # ref is a domain or arbitrary string — resolve via the domain graph
            ref_base = base_domain(ref)
            if ref_base:
                for c in companies:
                    own_bases = self._base_domains(c)
                    if ref_base in own_bases:
                        candidates.append((c, 0.97, "exact_domain", {"domain": ref_base}))
            # name-ish match attempt for non-domain refs
            if not candidates:
                ref_tokens = name_tokens(ref)
                for c in companies:
                    if not ref_tokens:
                        break
                    sim = jaccard(ref_tokens, name_tokens(c.legal_name))
                    if sim >= 0.75:
                        candidates.append((c, round(sim, 4), "token_similarity",
                                           {"legal_name_similarity": sim}))

        # dedupe candidates by company id keeping the best match
        best: dict[str, tuple[Company, float, str, dict]] = {}
        for c, conf, kind, compared in candidates:
            prev = best.get(c.id)
            if prev is None or conf > prev[1]:
                best[c.id] = (c, conf, kind, compared)

        for c, conf, kind, compared in best.values():
            matches.append({
                "company_id": c.id,
                "company_name": c.legal_name,
                "match_kind": kind,
                "confidence": conf,
                "compared_fields": compared,
                "domain": c.domain,
            })

        merge_proposals: list[dict] = []
        if source_company is not None:
            for m in matches:
                if m["confidence"] >= MERGE_THRESHOLD:
                    merge_proposals.append({
                        "keep_id": source_company.id,
                        "merge_id": m["company_id"],
                        "confidence": m["confidence"],
                        "rationale": f"same {m['match_kind']} signal "
                                     f"({m['compared_fields']}) — requires human confirmation",
                    })

        evidence = [
            {"kind": "record",
             "source_url": (f"https://{c.domain}" if c.domain else None),
             "excerpt": f"company {c.legal_name} (id {c.id}) matched by {k} @ {conf:.2f}"}
            for c, conf, k, _ in best.values()
        ]
        overall_conf = max((m["confidence"] for m in matches), default=0.0)
        return AgentResult(
            status="COMPLETED",
            output={
                "entity_kind": entity_kind,
                "query_ref": ref,
                "matches": matches,
                "merge_proposals": merge_proposals,
                "note": "Merge proposals always require human confirmation (never auto-merge).",
            },
            confidence=round(overall_conf, 4),
            evidence=evidence,
            tokens_in=0,
            tokens_out=0,
            cost_usd=0.0,
        )