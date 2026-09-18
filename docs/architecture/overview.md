# LeadSynt — Architecture Overview

LeadSynt is an event-driven sales-intelligence platform. Raw requirements/RFQs from
multiple sources enter as **tickets**, flow through a controlled pipeline of
stages (each agent's work audited and scored), and either convert to CRM
opportunities or are rejected with reasons. Humans stay in the loop; the system
never silently acts on unverified data.

## System map

```
                        ┌────────────────────────────────────────────┐
   Sources (official    │                LeadSynt                    │
   APIs/feeds, manual   │                                            │
   entry, webhooks) ───▶│  Next.js 14 frontend (React 18, TS)        │
   reply webhook ──────▶│  :3000  — login, dashboard, tickets, QA…   │
                        │     │  same-origin /api/* (rewrite proxy)  │
                        │  ┌──▼───────────────────────────────────┐  │
                        │  │ FastAPI backend :8000  /api/v1/*     │  │
                        │  │  JWT auth + RBAC + rate limiting     │  │
                        │  │  services → SQLAlchemy 2.0 models    │  │
                        │  │  Celery workers (jobs) + Redis       │  │
                        │  └──┬──────────────────┬────────────────┘  │
                        └─────┼──────────────────┼───────────────────┘
                              ▼                  ▼
                    SQL Server 2022        Redis (queues, cache,
                    (production)           rate limits, results)
                    SQLite (dev profile)
```

**Hard rule:** the frontend talks only to the API. There is no direct
database access from the browser, ever. All secrets (DB URL, JWT secret,
webhook secret, AI keys) exist only in backend environment variables.

## Technology choices

| Concern | Choice | Why |
|---|---|---|
| API | FastAPI + Pydantic v2 | typed schemas, async, OpenAPI |
| ORM | SQLAlchemy 2.0 (typed) | SQL Server dialect; same code runs on SQLite in dev |
| Migrations | Alembic | only allowed way to change schema |
| Auth | JWT (HS256) + bcrypt(12) | stateless, MFA-ready, role claims in token |
| Jobs | Celery + Redis | durable queue; beat for schedules; results backend |
| Frontend | Next.js 14 (App Router, TS) + Tailwind | SSR-capable, same-origin API proxy |
| DB (prod) | Microsoft SQL Server 2022 | target deployment |
| DB (dev) | SQLite | zero-dependency dev profile; schema is identical |
| Observability | /health, /health/ready, /metrics, JSON logs, audit table | |

## Request flow (typical read)

1. Browser → `GET /api/v1/tickets` (same-origin; Next rewrites to backend)
2. `AuthMiddleware` parses JWT, attaches user to request context (no DB hit)
3. `RateLimitMiddleware` checks per-user quota in Redis (429 on excess)
4. Router dependency `get_current_user` re-loads user + roles (DB)
5. `require_permission("tickets:read")` checks RBAC (403 on deny)
6. Service queries via ORM, returns Pydantic schema
7. `request_id` from the auth middleware is echoed in the response header
   and recorded in `RequestLog` (async fire-and-forget)

## Request flow (ticket creation)

1. `POST /api/v1/tickets` (permission `tickets:create`)
2. `TicketService.create()` opens **one transaction**:
   - upsert company / contact (privacy + consent defaults applied)
   - duplicate check (email + domain)
   - insert ticket + contacts + source + verification history placeholders
   - run scoring (`LeadScoringAgent` — deterministic, versioned, explainable)
   - create agent execution rows (provenance)
   - audit event `ticket.created`
3. Commit; 201 with the full ticket.

## Process model

| Process | Responsibility |
|---|---|
| `uvicorn app.main:app` | API; also runs on-demand jobs **in-process** when triggered via API |
| `celery worker` | durable execution of queued jobs; scheduled via beat |
| `celery beat` | schedules (connector refresh, QA sweep, freshness review, scoring) |
| Next.js (standalone `server.js`) | the public origin; proxies `/api/*` to the API |

**Single deployable:** `scripts/docker-entrypoint.sh` runs all four inside
one container (one image, one port — 3000): API on loopback:8000, worker +
beat as side processes, Next.js standalone in the foreground. Local dev uses
the same entrypoint via `scripts/dev_up.sh`; manual/hot-reload runs start
each process separately (see operations docs).

Why on-demand jobs run in-process: an on-demand API call should not depend on
worker availability; queued jobs (schedules, bulk work) always go through
Celery. Both paths share the same service functions
(`app/services/connector_service.py` is the canonical example), so behavior
is identical.

## Failure behavior

- DB down → health `degraded`/`error`, 503s for API routes that need DB; login still fails closed.
- Redis down → rate limiting degrades open (logged), health shows `error`, jobs rejected until it returns.
- Connector failure → `WebhookEvent`/`ConnectorRun` marked FAILED with error; never crashes the pipeline; QA sweep reports the failure.
- Bad transition / unknown data → structured 4xx with `code`, `message`, `request_id` — no silent fallbacks.
