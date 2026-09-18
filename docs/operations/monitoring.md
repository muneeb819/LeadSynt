# LeadSynt — Monitoring & Operations

## Liveness / readiness

| Endpoint | Meaning |
|---|---|
| `GET /api/v1/health` | process up; checks: `database`, `redis` (ok/error); version + environment |
| `GET /api/v1/health/ready` | `ready` only when DB query succeeds and Redis PONG; else 503 `not_ready` |

## Metrics

`GET /metrics` (Prometheus text format):

- `leadsynt_http_requests_total{method,path,status}`
- `leadsynt_http_request_duration_seconds`
- `leadsynt_db_pool_in_use / checked_out`
- `leadsynt_active_tickets{status}` (from `request_logs`-driven counters + ticket table)
- `leadsynt_agent_executions_total{agent,status}`
- `leadsynt_webhook_events_total{verification}`
- `leadsynt_qa_findings_open{severity}`

## Audit & request logs

- `request_logs` — one row per API request (user, method, path, status,
  ms, request_id) written asynchronously so it never adds latency on the hot path.
- `audit_logs` — business-level mutations with before/after JSON.
- Query both via `/admin/audit` (filtered) and directly in SSMS.

## QA sweep (data-integrity monitoring)

`POST /api/v1/qa/sweep` (also scheduled via beat) — 10 deterministic
categories; findings carry evidence + recommended action. Treat open
HIGH-severity findings as incidents. The sweep is itself tested
(`test_qa.py` — a seeded defect must be detected).

## Worker monitoring

- `celery inspect active / reserved / stats`
- Failed jobs are logged + the source `connector_runs`/`webhook_events` row
  is marked FAILED with the error (never silently dropped).
- Beat schedule (default, env-tunable):
  - `lead_synt.connector.refresh` — hourly
  - `lead_synt.qa.sweep` — every 6 h
  - `lead_synt.tickets.refresh_freshness` — every 2 h
  - `lead_synt.tickets.score_stale` — nightly
  - `lead_synt.health.check` — every 10 min

## Log formats

- Dev: human-readable lines with timestamp, level, module, request_id.
- Prod (`LEADSynt_LOG_JSON=true`): one JSON object per line
  `{ts, level, msg, module, request_id, user_id, ...extras}` — ship to any
  log aggregator (Loki/ELK) as-is.

## On-call runbook pointers

- API 503 `not_ready` → check `docker compose ps` / redis / mssql health;
  check `LEADSynt_DATABASE_URL` reachability (TCP 1433).
- 429 storms → verify per-user limits in settings; confirm no client loop.
- Connector FAILED rows → read `connector_runs.error`; re-run via
  `POST /sources/{key}/run`; check compliance notes if auth expired.
