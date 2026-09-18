# LeadSynt — Testing

## Layers

| Layer | Location | Count | What it proves |
|---|---|---|---|
| Unit/integration (API + services + DB) | `backend/app/tests/` | 70 | business rules on a real (in-memory SQLite) DB with full migrations |
| E2E (running stack) | `tests/e2e/foundation_check.py` | 24 checks | live API + DB + Redis behave end-to-end |
| Frontend build/type gate | `frontend` `npm run build` | — | TS strict compile + route generation |

## Backend suite

```bash
cd backend && .venv/bin/pytest app/tests -q
```

- `conftest.py`: fresh in-memory SQLite per test, `alembic` upgrade to head,
  FastAPI TestClient with dependency overrides, seeded admin/operator/viewer
  users, helper factories. **Close the Session in teardown, never the
  sessionmaker** (StaticPool pitfall).
- Coverage of the spec's required behaviors:
  - `test_duplicate_detection.py` — same email+domain → DUPLICATE; different → clean
  - `test_status_transitions.py` — legal paths OK; illegal → 409 `invalid_status_transition`
  - `test_verification.py` — valid/disposable/syntax-failed results; history appended
  - `test_suppression.py` — outreach 403 `suppressed_contact` for global + per-contact
  - `test_reply_handover.py` (13) — verbatim storage, automation stop, REPLIED→HOT_LEAD,
    dossier, owner notification, idempotent replay
  - `test_authz.py` — viewer 403 on create; admin can; anonymous 401
  - `test_audit.py` — every mutation produces a queryable audit row
  - `test_qa.py` — seeded defect (orphan verification row) must be found by the sweep
  - plus: auth/jwt, connectors, scoring, settings, pagination, health

## E2E check

```bash
backend/.venv/bin/python ../tests/e2e/foundation_check.py
```

Hits the **running** server: health → login → RBAC → pipeline → status
machine → verification → duplicates → QA → agents → settings → audit →
analytics. Exit 0 = ship-ready signal.

## Frontend

`npm run build` is the gate (strict TS). For a page you changed, also:
log in via the UI, confirm real data renders, confirm a 403 path shows the
error state (not a crash).

## Adding a test

1. Mirror the scenario name from the spec it covers.
2. Use the conftest factories; never depend on seeded dev data (suite runs
   on a blank DB).
3. Assert on **business outcome** (status code, DB row, audit row) — not on
   incidental field ordering.
4. If a test needs a "defect", create it explicitly in the test (QA category
   tests do this).

## Known pitfalls (learned the hard way)

- `db.get(Model, x)` is PK-only — use `select().where()` for slug lookups.
- `Mapped[list["X"]]` + explicit relationship target, or SQLAlchemy resolves
  `list` as an entity.
- `expire_on_commit=False` + string enums: normalize at write AND in
  serializers; compare with `==`, never `is`.
- After reassigning `status_id`, also set the `ticket.status` relationship
  (joined-load cache).
- FastAPI: a plain `db: Session` param without `Depends(get_db)` becomes a
  query param → 422.
- email-validator rejects special-use TLDs — use `@example.com`/`@leadsynt.io`
  in tests and seeds.
