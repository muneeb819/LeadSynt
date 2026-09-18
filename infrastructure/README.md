# LeadSynt — Infrastructure

Deployment infrastructure is **env-driven and IaC-first**. This directory
contains the provisioning artifacts; runtime config lives in `.env` (git-ignored).

## Contents

| File | Purpose |
|---|---|
| `terraform/main.tf` | Skeleton (Azure): MSSQL server + DB, Redis, storage for SQL backups. Apply only with a real subscription — no resources are created by this repo |
| `nginx/leadsynt.conf` | Reference reverse-proxy: TLS termination, CORS-safe same-origin layout, rate-limit zone, body limits |
| `sql/backup-restore.md` | Nightly MSSQL backup job + restore runbook (first step of the production hardening checklist) |
| `secrets/README.md` | Where secrets live (env/secret store) — never in this repo |

## Environments

| Env | DB | Notes |
|---|---|---|
| dev (local) | SQLite | zero-dependency; identical schema |
| docker (compose) | SQL Server 2022 | `../docker-compose.yml` |
| production | SQL Server 2022 (managed or VM) | Terraform skeleton + nginx + backups |

## Production topology

```
Internet → nginx (TLS 1.3, HSTS)
             └─ :3000  LeadSynt app container (the ONLY public port)
                        ├─ Next.js standalone (public origin)
                        ├─ API (loopback:8000, internal to the container)
                        └─ celery worker + beat
                             ├─ mssql 2022 (separate container, least-privilege login)
                             └─ redis (separate container)
```

The app ships as ONE image (root `Dockerfile`); the API and DB are
**never exposed to the internet** — only nginx → :3000. CORS is pinned to
the real origin via `LEADSynt_CORS_ORIGINS`.
