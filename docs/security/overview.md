# LeadSynt — Security Overview

## Authentication

- JWT **HS256**, access 60 min / refresh 7 days; secret from
  `LEADSynt_SECRET_KEY` (env-only; dev default is 64+ chars — pyjwt requires
  ≥ 32 bytes for HS256).
- Passwords: **bcrypt cost 12**, never logged, never returned.
- Token payload: `sub` (user id), `roles`, `exp`, `jti`. Refresh rotation:
  a used refresh token is rejected on reuse.
- **MFA-ready**: the user model + auth flow have a `mfa_enabled` seam; the
  foundation ships passwords-only (MFA is a later phase).
- Frontend stores tokens in `localStorage` (XOR-obfuscated) and attaches the
  Bearer header via the API client; on a hard 401 tokens are cleared → /login.

## RBAC

| Resource | admin | operator | viewer |
|---|---|---|---|
| tickets | CRUD + transition | create/transition/score | read |
| contacts / companies | full | full | read |
| sources / connectors | manage + run | run | read |
| verification | run | run | read |
| outreach | send (suppression-checked) | send | read |
| conversations / handover | full | create handover | read |
| deals / tasks / appointments | full | full | read |
| marketplace | full | list | read |
| analytics | full | full | read |
| agents | toggle + read | read + read runs | read |
| qa | full | sweep | read |
| settings | write | read | read |
| users | full | read | — |
| audit | read | read | — |

Enforced **server-side** in `app/auth/rbac.py` + `require_permission`
dependency. The frontend mirrors the matrix for UI gating only — the API is
authoritative (tested: viewer create → 403).

## Threat-surface controls

| Threat | Control |
|---|---|
| SQL injection | SQLAlchemy parameterized queries only; no raw string SQL in app code |
| XSS | React auto-escaping; no `dangerouslySetInnerHTML`; content from data is text-only |
| CSRF | pure Bearer-token API (no cookies) — CSRF not applicable; CORS restricted to `LEADSynt_CORS_ORIGINS` (dev: localhost:3000) |
| Brute force | per-user login rate limit (10/min) + general 120/min sliding window in Redis |
| Credential leak | secrets only in env vars; `.env` git-ignored; `.env.example` has no real values |
| Webhook spoofing | HMAC-SHA256 + timestamp replay window (see api/webhooks.md) |
| Prompt injection (AI phases) | agents get scoped `allowed_tools`; outputs schema-validated; no agent writes directly |
| Denial of service | pagination caps (page_size ≤ 100), body size limits via ASGI defaults |

## Audit trail

Append-only `audit_logs` (actor, action, entity, before/after JSON, request
id, ip). Written by every mutating service path. Query:
`GET /api/v1/admin/audit?action=ticket.created&limit=50`.
QA sweep includes an audit-integrity category.

## Secrets

| Variable | Purpose |
|---|---|
| `LEADSynt_SECRET_KEY` | JWT signing (≥ 64 chars recommended) |
| `LEADSynt_DATABASE_URL` | DB connection (never in code/DB itself) |
| `LEADSynt_REDIS_URL` / `LEADSynt_CELERY_*` | infra |
| `LEADSynt_WEBHOOK_SHARED_SECRET` | webhook HMAC |
| `LEADSynt_AI_API_KEY` | future LLM calls (optional now) |

Rule: nothing secret is ever sent to the browser; the Next.js proxy keeps the
backend origin server-side only.
