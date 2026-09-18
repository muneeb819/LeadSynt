# LeadSynt — Roadmap

## Built in this execution (phases 1–15, verified running)

- Repo structure, env-driven config, Docker deployment path (SQL Server 2022)
- FastAPI backend: auth (JWT/bcrypt), RBAC (3 roles), rate limiting, audit,
  request-id + request logs, structured errors, /metrics
- 46-table schema + Alembic migration (clean on fresh DB)
- Ticket pipeline: ingest → process → verify → score → status machine
  (21 statuses, controlled transitions)
- Connectors: registry + `dev_feed` implementation (compliant source),
  in-process + Celery execution, per-run audit
- Verification: email format/disposable checks with full history
- Scoring: explainable multi-signal lead score, immutable snapshots
- Reply webhook: HMAC-signed, replay-protected, full handover rule
  (automation stop → REPLIED/HOT_LEAD → dossier → owner notification)
- QA Master: deterministic sweep (10 categories) + findings API
- AI agent framework: 12 agents registered, execution/audit/cost plumbing
- Frontend: login + 16 working pages on real API data
- Tests: 70 backend tests + 24-check E2E; docs; README

## Next phases (interfaces ready, implementation pending)

### Phase A — AI implementations
1. LLM provider integration behind `LEADSynt_AI_API_KEY` (providers/models
   catalog tables exist).
2. Extraction agent (fact + provenance per item), intent agent,
   verification agent (evidence-backed), enrichment (licensed data).
3. Fraud & authenticity agent; entity resolution with company-domain graph.
4. Budget caps + per-agent dashboards (tables + API exist).

### Phase B — Outreach engine
1. Channel adapters (email first) behind the existing `outreach_messages`.
2. Template library + consent/suppression re-check at send time
   (suppression gate already enforced).
3. Reply routing hardening (multi-platform), follow-up rules with explicit
   human authorization (handover rule already blocks auto-follow-up).

### Phase C — Marketplace
1. Publishing workflow for `marketplace_items` (currently read surface).
2. Purchases + ratings, marketplace analytics.

### Phase D — CRM integration
1. CRM connector(s) via `crm_integrations` (two-way sync, field mapping,
   conflict rules), deals/appointments/tasks already modeled.

### Phase E — Operations maturity
1. MFA (seam exists), API keys (`api_keys` table exists) with scopes.
2. Retention job execution (currently sweep-flagged), archive workflow.
3. Observability: log ship, alerting rules on /health + QA HIGH findings.

## Standing design decisions (do not regress)

- Frontend → API only; DB access is server-side exclusively.
- Provenance mandatory; `UNKNOWN` over guessed values.
- Reply ⇒ stop automation ⇒ human handover (hard rule, tested).
- AI changes: request → plan → approval → apply → test → rollback.
- Compliant connectors only; no CAPTCHA/paywall/anti-bot bypass.
- Migrations via Alembic only; secrets via env only.
- Every fact about "what the system did" must be reconstructable from
  audit_logs + agent_executions + ticket_events.
