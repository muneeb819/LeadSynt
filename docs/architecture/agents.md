# LeadSynt — Agent Architecture

LeadSynt is agent-centric: every intelligence operation is an **agent** with a
stable identity, versioned logic, declared capabilities, and a complete
execution history. Agents never write to the database directly — they propose,
services apply, audit records everything.

## Agent model (`app/models/agent.py`)

| Field | Purpose |
|---|---|
| `agent_id` | stable slug, e.g. `lead-scoring` (lookup key) |
| `name` / `purpose` | human description |
| `version` | implementation version (bumped on logic change) |
| `system_instructions` | operating rules for the agent |
| `allowed_tools` | JSON list — the only actions this agent may request |
| `input_schema` / `output_schema` | JSON contracts |
| `model` / `temperature` / `max_tokens` | LLM config (null = deterministic, no LLM) |
| `is_active` | runtime kill-switch |
| `avg_confidence`, `total_executions`, `last_execution_at` | operational stats |

## Execution model

```
service calls run_agent(db, agent_id, input, evidence=None)
   └─▶ AgentExecution row (pending)
        └─▶ registry resolves implementation (AgentBase subclass)
             └─▶ execute() → AgentResult (data, confidence, evidence, metrics)
   └─▶ AgentExecution persisted with duration, tokens, cost, error
   └─▶ agent stats updated (avg confidence, execution count)
```

- **Deterministic agents** (scoring, QA sweep) cost zero tokens and are
  fully reproducible — the foundation ships these fully implemented.
- **LLM agents** (scout, extraction, intent, verification, fraud, enrichment,
  outreach, handover, QA advisory) use the registry contract with
  `model`/`temperature`/`max_tokens`; their `execute()` implementations land in
  later phases (see roadmap). The interface, audit, and fail-safe plumbing is
  in place and tested.
- If no implementation is registered, `run_agent` records a **failed execution
  with a clear error** instead of fabricating output. `GET /api/v1/agents`
  exposes `has_implementation` per agent so the UI can say so honestly.

## The 12 registered agents

| agent_id | Phase status | Role |
|---|---|---|
| `scout` | interface ready | discovers new opportunities in compliant sources |
| `market-intelligence` | interface ready | sector/context analysis attached to tickets |
| `extraction` | interface ready | structured facts from raw payloads (provenance per fact) |
| `intent` | interface ready | intent level / urgency / budget signals |
| `entity-resolution` | interface ready | matches companies/contacts to CRM records |
| `verification` | interface ready | contact/company authenticity checks, evidence-backed |
| `enrichment` | interface ready | fills missing fields from licensed data, marked as enriched |
| `fraud-authenticity` | interface ready | flags suspicious/duplicate/low-authenticity entries |
| `lead-scoring` | **fully implemented** | explainable multi-signal score (see below) |
| `outreach` | interface ready | generates/controls outreach; stops on reply |
| `handover` | interface ready | builds human-handover dossiers |
| `qa-master` | **sweep implemented** | deterministic data-QA sweep + advisory findings |

## Scoring (implemented, explainable)

`app/services/scoring_service.py` runs via the `lead-scoring` agent. Components
(immutable, versioned snapshots in `TicketScoreHistory`):

```
intent_score  = intent_level(10-40) + urgency(0-20) + budget(10) + fresh≤48h(10)
lead_score    = intent×0.5 + verified(15) + freshness(15/8/0)
              + budget(15) + requirement≥80ch(10) + classified(5)        → 0..100
risk_score    = 5 + unverified(15) + duplicate(15) + no_url(10) + no_date(5)
confidence    = known_fields / 6
```

Every snapshot stores `components` JSON + the agent execution id — a score is
always explainable, never a black box.

## QA Master (implemented: deterministic sweep)

`app/services/qa_service.py::run_qa_sweep` checks 10 categories — orphan
verification rows, stale active tickets, tickets missing provenance,
verification failures without history, outreach active without suppression
check, missing scores on qualified tickets, webhook failures, duplicate
domains, unassigned hot leads, status-machine anomalies.

Every finding carries: `severity`, `evidence` (real rows/IDs), `root_cause_hypothesis`,
`recommended_action`, `affected_component`, `test_recommendation`, `status`.
Findings are re-runnable: a fixed issue changes status, the sweep never
invents issues to fill a report.

## Guardrails for AI (all phases)

1. No agent has unrestricted database write access — services own writes.
2. Any model-proposed change follows: **request → plan → approval → apply → test → rollback**.
3. LLM output is validated against `output_schema`; schema-invalid output = failed execution, never stored as data.
4. Hallucination fail-safe: extraction/verification agents may only assert facts present in the input evidence; missing → `UNKNOWN`.
5. Every execution: tokens, cost, duration, error, confidence — stored and queryable (`/api/v1/agents/{id}/runs`).
6. Agent kill-switch: `is_active=false` (admin UI/API) stops it everywhere.
