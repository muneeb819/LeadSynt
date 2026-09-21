# LeadSynt

![CI](https://github.com/muneeb819/LeadSynt/actions/workflows/ci.yml/badge.svg)

**Event-driven sales-intelligence platform.** Requirements and RFQs from
compliant sources enter as tickets, flow through an audited pipeline
(discovery → verification → scoring → outreach → human handover), and become
CRM opportunities — with provenance on every fact and a human in the loop.

> Foundation build (phases 1–15 of the master spec): running frontend +
> backend + database + job system + 12-agent architecture + QA master +
> full test suite. AI agent implementations, outreach engine, and
> marketplace publishing land in later phases — their interfaces are already
> in place. See [docs/roadmap.md](docs/roadmap.md).

## Live status

| Component | Stack | Port |
|---|---|---|
| Frontend | Next.js 14 (App Router, TS, Tailwind) | **3000 — the only public port** |
| API | FastAPI + Pydantic v2 + SQLAlchemy 2.0 | 8000 (loopback inside the app) |
| Jobs | Celery + Redis (worker + beat) | — |
| Database | SQL Server 2022 (prod) / SQLite (dev profile) | 1433 (compose only) |

**One project, one deployable:** the root `Dockerfile` packs frontend + API +
worker + beat into a **single image on a single port (3000)**; the browser
only ever talks to that port. Everything is env-driven (`LEADSynt_` prefix,
see `.env.example`). No secrets in code.

## Quick start (local, no Docker)

```bash
./scripts/dev_up.sh          # one command: venv + build + redis + API + worker + frontend
# → http://localhost:3000
```

Or with Docker (real SQL Server 2022) — **one image, one port**:

```bash
cp .env.example .env         # fill the 4 required secrets
docker compose up --build    # db + redis + the whole app on :3000
```

### Manual development (hot reload)

```bash
# 1. backend
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt
cd backend && cp ../.env.example .env          # set LEADSynt_SECRET_KEY (64+ chars)
mkdir -p ../database/dev
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --port 8000 --reload   # seeds roles/users/agents on boot

# 2. worker + beat (for scheduled jobs)
.venv/bin/celery -A app.workers.celery_app:celery worker --loglevel=info
.venv/bin/celery -A app.workers.celery_app:celery beat

# 3. frontend (hot reload; /api/* proxies to :8000)
cd ../frontend && npm install && npm run dev   # :3000
```

Dev logins (seeded): `admin|operator|viewer@leadsynt.io` /
`LeadSynt-Dev-Only-2026`

Produce real pipeline data: `POST /api/v1/sources/dev_feed/run` (admin token)
→ the dev feed connector ingests 10 items through the full pipeline
(duplicates, scoring, audit included).

> Deployment details: [docs/operations/docker.md](docs/operations/docker.md)
> and [docs/operations/local-dev.md](docs/operations/local-dev.md).

## Verify

```bash
cd backend
.venv/bin/pytest app/tests -q                 # 70 tests
.venv/bin/python ../tests/e2e/foundation_check.py   # 24 live-stack checks
cd ../frontend && npm run build               # TS strict gate
```

## The ticket — central object

Each ticket carries: identity (reference, status), contact + company
references, strategic context (intent, urgency, budget, sector), source
provenance (URL, discovered when/by), intelligence (lead/intent/risk scores
with immutable component-level history), verification history, conversation,
outreach state, and CRM linkage.

**Status machine** (21 statuses, controlled transitions, illegal → 409):
`DISCOVERED → INGESTED → PROCESSING → VERIFIED → QUALIFIED →
OUTREACH_ACTIVE → REPLIED → HOT_LEAD → HUMAN_HANDOVER → OPPORTUNITY → WON/LOST`
plus `DUPLICATE / NEEDS_REVIEW / DISQUALIFIED / ARCHIVED` and pipeline states.

**Critical rule (implemented + tested):** a reply stops automated outreach
immediately, moves the ticket to REPLIED/HOT_LEAD, creates a handover
dossier, and notifies the owner. No auto-follow-up without explicit human
authorization.

## Key endpoints (49 total — `GET /api/v1/docs`)

```
POST /auth/login            GET  /tickets  (filters, pagination, sort)
GET  /auth/me               GET  /tickets/{id}   (provenance + scores)
POST /tickets               POST /tickets/{id}/status
POST /sources/{key}/run     POST /verification/email
GET  /leads                 POST /qa/sweep          GET /qa/findings
GET  /agents  GET /agents/{id}/runs
GET  /analytics/dashboard   GET  /analytics/pipeline
POST /webhooks/reply        (HMAC-signed, replay-protected)
GET  /health  /health/ready /metrics
```

Error contract: `{ "error": { "code", "message", "details", "request_id" } }`.

## Repository layout

```
One project folder. One deployable.
Dockerfile          single image: frontend + API + worker + beat → port 3000
docker-compose.yml  db (mssql 2022) + redis + the app
frontend/           Next.js app (login, dashboard, tickets, leads, contacts,
                    companies, agents, QA, analytics, sources, settings, admin, …)
backend/            FastAPI app: api/ auth/ models/ schemas/ services/ agents/
                    connectors/ workers/ webhooks/ security/ audit/ monitoring/
                    configuration/ tests/ + alembic/
database/           dev SQLite + dev feed (prod = SQL Server via compose)
docs/               architecture, database, API, security, privacy, ops, dev, AI
tests/e2e/          live-stack foundation check
scripts/            dev_up.sh (one-shot local run), docker-entrypoint.sh,
                    seed_dev.py (idempotent)
```

## Documentation

Start at **[docs/README.md](docs/README.md)** — architecture, schema,
migrations, API + webhooks, security/privacy, operations (local + docker +
monitoring), development guides, AI subsystem, roadmap.

## Principles (non-negotiable)

- **Provenance on every fact** — source URL, discovered/verified when+by,
  confidence. `UNKNOWN` over a guess, always.
- **Auditable** — `audit_logs` + `agent_executions` + `ticket_events`
  reconstruct any decision.
- **AI has no unrestricted power** — agents propose; services apply;
  changes follow request → plan → approval → apply → test → rollback.
- **Compliant connectors only** — official APIs, permitted pages, feeds,
  licensed data. No CAPTCHA/paywall/anti-bot bypass.
- **Privacy by construction** — consent flags, suppression/DO-NOT-CONTACT
  hard-blocks outreach, retention window, audited privacy actions.
