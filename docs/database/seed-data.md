# LeadSynt — Seed Data

Seeding is **idempotent** and clearly labeled: it runs at API startup
(lifespan) in the dev environment and is also available as a script.

## What gets seeded

| Item | Details |
|---|---|
| Roles | `admin`, `operator`, `viewer` (permission matrix in `app/auth/rbac.py`) |
| Users | 3 dev users with bcrypt-hashed passwords (never stored in code) |
| Agents | 12 agent definitions (see `app/agents/registry.py`) |
| Settings | default dynamic settings (outreach rules, scoring weights display, retention days) |
| Connectors | registry rows incl. `dev_feed` (the only data connector in the foundation) |

## Dev credentials

| Role | Email | Password |
|---|---|---|
| admin | `admin@leadsynt.io` | `LeadSynt-Dev-Only-2026` |
| operator | `operator@leadsynt.io` | `LeadSynt-Dev-Only-2026` |
| viewer | `viewer@leadsynt.io` | `LeadSynt-Dev-Only-2026` |

> Dev-only. Production requires `LEADSynt_SEED_ADMIN_*` and disables
> self-registration (`LEADSynt_ALLOW_SELF_REGISTRATION=false`).

## How the dev tickets were produced (no fake pipeline data)

The 10 dev tickets in `database/dev/leadsynt_dev.db` were **not hand-inserted**.
They were created by running the real pipeline:

1. `POST /api/v1/sources/dev_feed/run` (in-process) → the `dev_feed` connector
   ingested a 10-item synthetic-but-declared feed (`database/dev_feed.json`)
   as `SourceItem` rows with full provenance.
2. `TicketService.process_source_items()` created tickets through the normal
   create path: duplicate checks, contacts/companies upsert, scoring agent,
   audit events.
3. One ticket (`TS-202609-0001`) was driven through outreach → a signed
   reply webhook (`POST /api/v1/webhooks/reply`) → REPLIED → HOT_LEAD →
   `HUMAN_HANDOVER` with dossier, proving the critical handover rule live.

Re-running the connector is safe: content-hash dedupe yields
`found=10, new=0, duplicates=10`.

## Reset the dev environment

```bash
rm database/dev/leadsynt_dev.db
alembic upgrade head        # recreate schema
# restart API — lifespan re-seeds users/agents/settings/connectors
python ../scripts/seed_dev.py
POST /api/v1/sources/dev_feed/run   # re-run the pipeline
```
