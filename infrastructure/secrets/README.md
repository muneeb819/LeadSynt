# Secrets — where they live

**This directory intentionally contains no secrets and never will.**

| Secret | Dev | Production |
|---|---|---|
| JWT signing key | `backend/.env` (`LEADSynt_SECRET_KEY`) | secrets manager / CI variable, injected as env |
| DB credentials | `backend/.env` | secrets manager + least-privilege MSSQL login |
| Webhook HMAC secret | `backend/.env` | secrets manager; rotate via `settings` + webhook docs |
| AI provider keys | `backend/.env` (optional) | secrets manager |
| TLS private keys | — | nginx host / cert manager, never in repo |

Rules:
1. Secrets enter the system **only as environment variables** (12-factor).
2. `.env` files are git-ignored; `.env.example` ships with placeholders only.
3. Rotation: change the value in the secret store → restart services; JWT
   rotation invalidates sessions (by design — announce in advance).
4. If a secret is found in code, logs, or the DB: rotate it first, forensics
   second.
