# LeadSynt — AI Subsystem

## Design principles

1. **No agent has unrestricted power.** Agents propose; services apply;
   every step is audited.
2. **Provenance or nothing.** An agent output without evidence is `UNKNOWN`,
   never a guess stored as fact.
3. **Explainable by default.** Scores carry component breakdowns; findings
   carry evidence + root-cause hypothesis + recommended action + test.
4. **Cost is tracked.** Every execution records tokens, cost, duration —
   queryable per agent and per ticket.
5. **Reproducible where possible.** Deterministic agents (scoring, QA sweep)
   are implemented first and carry zero token cost; LLM agents are wrapped
   behind the same contract so swapping implementations changes nothing
   downstream.

## Execution pipeline

```
service → run_agent(db, agent_id, input, evidence)
        → AgentExecution(pending)
        → AgentBase.execute()  [registry: agent_id → implementation]
        → AgentResult { data, confidence, evidence, metrics }
        → validate against output_schema
        → AgentExecution(success/failed) + stats + ai_usage ledger row
```

Failure modes (all recorded, none silent): unregistered implementation →
failed execution "no implementation registered"; schema-invalid output →
failed; exception → failed with traceback in `error`.

## Guardrails for LLM agents (binding for all phases)

- **Hallucination fail-safe**: extraction/verification agents may only
  assert facts present in the provided input evidence. Missing → `UNKNOWN`.
- **Scope**: each agent's `allowed_tools` is a closed list; anything else
  requires a new agent definition + approval.
- **Change workflow**: a model-proposed mutation (e.g. "change status to X")
  is a *request* — it goes request → plan → approval → apply → test →
  rollback, never direct write.
- **Prompting**: prompts live in `agent_prompts` (versioned). Rules baked
  into every system prompt: state confidence; cite evidence per fact;
  output only the declared JSON schema; never invent URLs, emails, or names.
- **Budgets**: per-agent `max_tokens` + per-day cost caps from
  `settings` (`ai.daily_budget_usd`); exceeding → execution refused,
  finding emitted.

## Prompt template (canonical, all agents)

```
You are {name} (v{version}) inside LeadSynt.
Purpose: {purpose}
You may only use: {allowed_tools}.
Respond with JSON matching: {output_schema}
Rules:
1. Base every field ONLY on the provided input and evidence.
2. Missing information → value "UNKNOWN" and lower confidence.
3. Include "evidence" per asserted fact (source reference from input).
4. Never invent URLs, emails, names, or numbers.
5. State your confidence 0..1 and justify it in "confidence_reason".
Input: {input_json}
Evidence: {evidence_json}
```

## Cost tracking

`ai_usage` rows: `(execution_id, agent_id, model, prompt_tokens,
completion_tokens, cost_usd, ts)`. `GET /api/v1/agents/{id}/runs` exposes
per-run metrics; `/analytics/dashboard` can surface spend trends.

## Current state (foundation)

- `lead-scoring`: fully implemented, deterministic (see architecture/agents.md).
- `qa-master`: deterministic sweep implemented (10 categories).
- Remaining 10 agents: definition rows + registry contract + execution/
  audit plumbing live and tested; `execute()` lands in later phases with
  real providers behind `LEADSynt_AI_API_KEY`.
