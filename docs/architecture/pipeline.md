# LeadSynt — Intake Pipeline & Status Machine

## Pipeline stages (event-driven)

Data never flows "scraper → table → dashboard". Every record moves through
explicit stages, each emitting audit events and carrying provenance:

```
SOURCE CONNECTOR / MANUAL ENTRY / WEBHOOK
        │  SourceItem (raw payload + provenance, content hash)
        ▼
INGESTION ──────────────────► ticket.status = INGESTED
        │   duplicate check (email+domain) ──► DUPLICATE / NEEDS_REVIEW
        ▼
PROCESSING (entity extraction, contact/company upsert)
        ▼
VERIFICATION (email/format checks, verification history per attempt)
        │   every attempt stored: type, result, confidence, method, evidence
        ▼
QUALIFIED ──► OUTREACH_ACTIVE (automated outreach, if authorized)
        │
        ├── REPLIED ──► HOT_LEAD (positive sentiment) ──► HUMAN_HANDOVER
        ▼
OPPORTUNITY ──► WON / LOST
        └── anywhere ──► DISQUALIFIED / ARCHIVED (reason required via audit)
```

## Status machine (21 statuses, controlled transitions)

Defined in `backend/app/models/ticket.py` (`TicketStatus` + `ALLOWED_TRANSITIONS`).
`TicketService.change_status()` is the **only** writer:

- illegal transition → `409 invalid_status_transition` (structured error)
- transition to the current status → `400 no_status_change`
- every change → `AuditLog(status_changed)` with before/after + actor

| Status | Meaning |
|---|---|
| DISCOVERED | first seen by a connector |
| INGESTED | normalized into a ticket |
| PROCESSING | being normalized/extracted |
| VERIFIED | identity checks passed |
| QUALIFIED | scored and worth pursuing |
| OUTREACH_ACTIVE | automated outreach running |
| REPLIED | counterparty replied (automation STOPPED) |
| HOT_LEAD | replied + positive sentiment |
| HUMAN_HANDOVER | dossier prepared, assignee notified |
| OPPORTUNITY | in CRM pipeline |
| WON / LOST | terminal deal states |
| DUPLICATE | folded into an existing ticket |
| NEEDS_REVIEW | humans should look |
| DISQUALIFIED | not viable (reason recorded) |
| ARCHIVED | retired |
| + internal states (ENRICHED, SCORED, FOLLOWUP_DUE, …) | pipeline bookkeeping |

## Reply-handover rule (critical, tested)

When a reply webhook is received for an active ticket:

1. Reply stored verbatim on the ticket conversation (never paraphrased).
2. **Automated outreach for that ticket is stopped immediately** —
   `outreach.automation_paused` audit event, flag persisted.
3. Status → `REPLIED`; if sentiment is positive and the ticket was
   `OUTREACH_ACTIVE` → `HOT_LEAD`.
4. `HUMAN_HANDOVER` event created with a **dossier** (ticket, contacts,
   company, timeline, provenance, score history).
5. Notification to the ticket owner (`owner_id`).
6. No further automatic follow-up — ever — until a human explicitly
   authorizes it (permission-gated API call).

Implemented in `app/webhooks/inbox.py` + `app/services/outreach_service.py`;
covered by `test_reply_handover.py` (13 tests) and the live webhook flow.

## Provenance (non-negotiable)

Every discovered fact carries:

- `original_url` — where it was found
- `discovered_at` + `discovered_by` (connector key or user)
- `verified_at` / `verified_by` + `verification_history` rows
- `confidence` (0–1) — `UNKNOWN`/`UNVERIFIED` values are explicit, never guessed

`SourceItem.content_hash` dedupes identical payloads; `ConnectorRun` rows keep
per-run counts (found / new / duplicates / errors).

## Freshness

`tickets.refresh_freshness` (Celery + beat, and on-demand) recomputes
`stale` flags from `discovered_at` and moves stale active tickets to
`NEEDS_REVIEW`. QA sweep reports stale/missing-freshness data as findings.
