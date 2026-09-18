# LeadSynt Documentation

Documentation for the LeadSynt foundation (phases 1–15 of the master spec).
Everything here describes **implemented, verified behavior** — not aspirations.

## Architecture

| Document | Contents |
|---|---|
| [architecture/overview.md](architecture/overview.md) | System map, service boundaries, tech stack, request flow |
| [architecture/pipeline.md](architecture/pipeline.md) | Event-driven intake pipeline, stages, status machine, handover rule |
| [architecture/agents.md](architecture/agents.md) | Agent model, 12 registered agents, execution model, provenance |

## Database

| Document | Contents |
|---|---|
| [database/schema.md](database/schema.md) | All 46 tables by group, key invariants |
| [database/migrations.md](database/migrations.md) | Alembic workflow (the only way to change schema) |
| [database/seed-data.md](database/seed-data.md) | Dev seeds, credentials, how data was produced |

## API

| Document | Contents |
|---|---|
| [api/overview.md](api/overview.md) | All 49 endpoints, conventions, pagination, error contract |
| [api/webhooks.md](api/webhooks.md) | Reply webhook: signing, replay protection, failure handling |

## Security & Privacy

| Document | Contents |
|---|---|
| [security/overview.md](security/overview.md) | JWT, RBAC matrix, rate limiting, audit trail, secrets |
| [privacy.md](privacy.md) | Consent, suppression/DO-NOT-CONTACT, retention, outreach gating |

## Operations

| Document | Contents |
|---|---|
| [operations/local-dev.md](operations/local-dev.md) | Run everything locally (no Docker required) |
| [operations/docker.md](operations/docker.md) | Full stack incl. real SQL Server 2022 via compose |
| [operations/monitoring.md](operations/monitoring.md) | Health endpoints, /metrics, QA sweep, logs |

## Development

| Document | Contents |
|---|---|
| [development/backend.md](development/backend.md) | FastAPI structure, service layer, connectors, workers |
| [development/frontend.md](development/frontend.md) | Next.js structure, API client, pages |
| [development/testing.md](development/testing.md) | 70-test suite layout, E2E check, how to add tests |

## AI

| Document | Contents |
|---|---|
| [ai/agents.md](ai/agents.md) | Agent architecture, fail-safes, prompting rules, cost tracking |

## Roadmap

| Document | Contents |
|---|---|
| [roadmap.md](roadmap.md) | What is built, what comes in later phases, design decisions for them |
