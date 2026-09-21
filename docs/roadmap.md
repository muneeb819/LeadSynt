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
- **Phase A complete**: `ai_providers`/`ai_models` catalog (idempotent seed,
  resolve_llm_config), six new agent engines (extraction, intent, verification,
  enrichment, fraud & authenticity, entity resolution) — deterministic without
  an API key, LLM-backed when `LEADSynt_AI_PROVIDER` is set, never fabricating
  data; monthly budget caps (`monthly_budget_usd`, cancelled runs + audit);
  run API (`POST /agents/{id}/run`) and per-agent dashboards
  (`/agents/analytics`, `/agents/providers`, `/agents/models`); frontend agents
  dashboard with budget bars, run control and provider/model catalog
- Frontend: login + 16 working pages on real API data
- Tests: 70 backend tests + 24-check E2E; docs; README
- **Phase B complete**: outreach engine — `outreach_messages` +
  `outreach_templates` + `follow_up_rules` + `outreach_follow_up_authorizations`
  schema (migration `b0a1e2f3c4d5`); email channel adapter (`log` transport
  marks QUEUED without ever claiming external delivery; SMTP transport is real
  and only used when configured); deterministic template library seeded at
  startup (`email-sequence-1..3`) with UNKNOWN-over-guess rendering and a
  mandatory opt-out footer; mandatory send-time gatechain re-checked live on
  every send (suppression → consent → reply-pause/handover → daily cap →
  quiet hours, each BLOCKED state audited `outreach.blocked:<reason>`); reply
  routing hardening (`/webhooks/reply` resolves by ticket/thread/sender, honors
  explicit opt-outs as audited suppressions, rejects unsupported channels);
  follow-up rules with explicit human authorization
  (`POST /outreach/follow-ups/authorize`, audited, `sequence <= max_follow_ups`);
  `outreach-ai` agent (read-only drafts + live suppression re-check); Celery
  `leadsynt.outreach.send_due`; outreach API + RBAC (`outreach:read/send/manage`)

## Next phases (interfaces ready, implementation pending)

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
