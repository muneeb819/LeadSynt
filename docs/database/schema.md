# LeadSynt — Database Schema (46 tables)

Single Alembic revision `ed1b5a8cff29` creates the foundation schema.
Target dialect: **Microsoft SQL Server 2022** (works on SQLite in the dev
profile — identical SQLAlchemy models).

## Table groups

### Core (tickets — the central object)
| Table | Purpose |
|---|---|
| `tickets` | requirement/RFQ ticket; identity (reference `TS-YYYYMM-NNNN`), status, intent/urgency/budget, scores, flags (stale, suppressed), ownership, timestamps |
| `ticket_contacts` | ticket ↔ contact (role) |
| `ticket_companies` | ticket ↔ company (role: primary/vendor/partner) |
| `ticket_sources` | provenance: platform, original_url, discovered_at/by |
| `ticket_score_histories` | immutable score snapshots (lead/intent/risk/confidence + components JSON) |
| `ticket_notes` | internal notes with author |
| `ticket_events` | append-only pipeline event stream |

### Pipeline support
| Table | Purpose |
|---|---|
| `source_items` | raw inbound payloads; content_hash dedupe; status (NEW/PROCESSED/FAILED) |
| `verification_histories` | every verification attempt (type, result, confidence, method, evidence) |
| `outreach_campaigns` / `outreach_messages` | campaign + per-ticket message log (status, sent/read/replied) |
| `conversations` / `conversation_messages` | human+machine conversation threads; replies stored verbatim |
| `handover_events` | HUMAN_HANDOVER dossiers (payload JSON, assignee, notification id) |

### CRM & people
| Table | Purpose |
|---|---|
| `contacts` | person: name, title, emails/phones, consent flag, `is_suppressed` (DO-NOT-CONTACT) |
| `companies` | legal_name, domain, industry, size, website |
| `company_domains` | domain ↔ company mapping (uniqueness + duplicate detection) |
| `deals` | CRM deals (stage, value, currency, close date) |
| `appointments` | meetings/tasks around tickets |
| `tasks` | follow-up tasks with due dates + owner |

### Marketplace
| Table | Purpose |
|---|---|
| `marketplace_items` | published/listed requirements |
| `marketplace_categories` | taxonomy |
| `marketplace_purchases` / `marketplace_ratings` | purchase + rating records |

### Integrations
| Table | Purpose |
|---|---|
| `crm_integrations` | CRM system connections (type, config JSON, status) |
| `connectors` | connector registry rows (key, name, auth method, schedule, rate limit, compliance notes, health) |
| `connector_runs` | per-run results (found/new/duplicates/failed, error, duration) |
| `webhook_events` | inbound webhook envelope + verification result (SIGNED/FAILED) + processing status |
| `ai_providers` / `ai_models` | provider/model catalog with cost config |
| `ai_usage` | per-execution token + cost ledger |

### AI agents
| Table | Purpose |
|---|---|
| `ai_agents` | agent definitions (see architecture/agents.md) |
| `agent_executions` | every run: input/output refs, duration, tokens, cost, confidence, error |
| `agent_prompts` | versioned prompt templates |
| `agent_versions` | version history |

### Platform / governance
| Table | Purpose |
|---|---|
| `users` | auth subjects (email unique, hashed password, active) |
| `roles` / `user_roles` | RBAC (admin/operator/viewer) |
| `permissions` | catalog of `resource:action` permissions |
| `audit_logs` | append-only: actor, action, entity, before/after JSON, request id |
| `settings` | dynamic configuration (key, JSON value, description, who can edit) |
| `notifications` | in-app + email notification log (type, target, read) |
| `request_logs` | per-request observability (method, path, status, latency, user, request_id) |
| `api_keys` | programmatic access (hashed, scoped, rate-limited) |
| `suppression_list` | global DO-NOT-CONTACT list (email/domain, reason, source) |

## Invariants (enforced by service layer + tests)

1. `tickets.reference` unique, generated `TS-YYYYMM-NNNN`.
2. Status changes only via `TicketService.change_status` (transition map).
3. `verification_histories.ticket_id` must reference a live ticket (QA-checked).
4. `contacts.is_suppressed` / `suppression_list` block outreach (403 `suppressed_contact`).
5. Score rows are append-only (no UPDATE on `ticket_score_histories`).
6. `agent_executions` and `audit_logs` are append-only.
