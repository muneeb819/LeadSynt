# LeadSynt — Backend Development Guide

## Layout

```
backend/app/
  main.py            # app factory, lifespan seeding, error handlers, /metrics
  core/              # config (env-prefixed), database, security, exceptions,
                     # logging, middleware (auth/rate-limit/request-id), pagination
  api/v1/            # 19 routers under /api/v1 (thin: parse → service → schema)
  api/deps.py        # get_current_user, require_permission, pagination deps
  auth/              # JWT create/verify, password hash, rbac matrix
  models/            # SQLAlchemy 2.0 typed models (14 modules, 46 tables)
  schemas/           # Pydantic request/response schemas (one module per domain)
  services/          # business logic — the ONLY layer that writes to the DB
  agents/            # AgentBase + registry (12) + lead_scoring implementation
  connectors/        # base class + registry; dev_feed implementation
  workers/           # celery app + tasks (thin wrappers over services)
  webhooks/          # signed reply ingestion
  security/          # HMAC helpers
  notifications/     # in-app notification writer
  audit/             # audit event helper
  monitoring/        # metrics registry
  configuration/     # dynamic settings service
  tests/             # 70 pytest tests (see development/testing.md)
alembic/             # migrations (ONLY way to change schema)
```

## Rules that keep it maintainable

1. **Routers stay thin.** No business logic in `api/`. If you need a second
   function, it belongs in a service.
2. **Services own transactions.** One commit per business operation; roll
   back on any failure; audit inside the transaction.
3. **Repositories/services split**: the foundation uses services directly;
   the `repositories/` package is reserved for read-heavy query aggregation
   as the schema grows (see roadmap).
4. **Models are SQL-Server-first.** Avoid SQLite-only types; use `String`,
   `DateTime(timezone=True)`, `JSON` (mapped to NVARCHAR(max) on SQL Server
   where needed).
5. **Enums**: store string values; normalize at assignment AND in serializers
   (SQLAlchemy may hand back the raw string after commit).
6. **New domain object**: model → alembic autogenerate → review → schema
   (Pydantic) → service → router → frontend service+page → test.
7. **Env-driven everything** via `app/core/config.py` (`LEADSynt_` prefix).
   No hardcoded hosts, ports, or secrets anywhere.

## Adding a service

```python
# app/services/example_service.py
class ExampleService:
    def __init__(self, db: Session):
        self.db = db

    def do_thing(self, user: User, **kw) -> SomeSchema:
        # validate → mutate → audit → return schema
```

Wire it into a router via dependency-injected `db: Session = Depends(get_db)`
and `require_permission("example:do")`.

## Adding a connector

Subclass `app/connectors/base.py::BaseConnector`, `@register("my_source")`,
implement `fetch() -> list[SourceItemPayload]`. Import the module from
`app/connectors/__init__.py` so the registry populates in every process
(API, worker, beat). Add a `connectors` registry row with auth method,
schedule, rate limit, and compliance notes.

## Adding a job

Define the Celery task in `app/workers/tasks.py` as a thin wrapper around a
service function. On-demand API triggers execute the same service function
**in-process** (worker availability must not gate a synchronous API call);
beat schedules enqueue through Celery.
