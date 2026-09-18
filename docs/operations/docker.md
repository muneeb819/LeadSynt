# LeadSynt — Docker Deployment

**One project → one image → one port.** The root `Dockerfile` builds a single
image containing the frontend (Next.js standalone), the API (FastAPI), the
Celery worker and beat. The only public port is **3000** — the Next server
proxies `/api/*` to the API on loopback inside the container. The API and the
database are never exposed to the network.

## Run the whole platform

```bash
cp .env.example .env      # set: LEADSynt_SECRET_KEY, LEADSynt_SEED_ADMIN_EMAIL,
                          #      LEADSynt_SEED_ADMIN_PASSWORD, LEADSynt_WEBHOOK_SHARED_SECRET
docker compose up --build # = db (SQL Server 2022) + redis + leadsynt
```

Or the bare app image (bring your own SQL Server + Redis endpoints via env):

```bash
docker build -t leadsynt .
docker run -p 3000:3000 --env-file .env leadsynt
```

Open http://localhost:3000.

## What `docker compose` starts

| Service | Contents | Published port |
|---|---|---|
| `db` | mcr.microsoft.com/mssql/server:2022 (volume `mssql-data`, sqlcmd healthcheck) | 1433 |
| `redis` | redis:7 (broker db1, results db2, rate limits db0) | — |
| `leadsynt` | **the whole app**: Next.js :3000 (public) → API 127.0.0.1:8000 + celery worker + beat | **3000** |

The `leadsynt` container boot sequence (`scripts/docker-entrypoint.sh`):

1. `alembic upgrade head` — schema current before anything serves traffic
2. uvicorn on **127.0.0.1:8000** (loopback only)
3. readiness gate (waits for `/api/v1/health/ready`)
4. celery worker + beat
5. Next.js standalone `server.js` on **0.0.0.0:3000** (foreground)

## Scaling out later

The single container is the default for small/mid deployments. When you need
independent scaling, split the same processes into services (compose
`deploy` or k8s): the entrypoint's steps 2/4/5 map 1:1 to containers —
point the frontend's `BACKEND_URL` at the API service address (build arg).

## Production hardening checklist

- [ ] Strong random `LEADSynt_SECRET_KEY` (32+ bytes) and webhook secret
- [ ] MSSQL SA password rotated; app uses a least-privilege login
- [ ] TLS in front of :3000 (see `infrastructure/nginx/leadsynt.conf`)
- [ ] CORS pinned to the real origin (`LEADSynt_CORS_ORIGINS`)
- [ ] Nightly MSSQL backup + tested restore (`infrastructure/sql/backup-restore.md`)
- [ ] Alerting on `/api/v1/health/ready` 503s and QA HIGH findings
