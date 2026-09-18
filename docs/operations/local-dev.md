# LeadSynt — Local Development (no Docker)

## One-shot (same code path as the container)

```bash
./scripts/dev_up.sh
```

Prepares whatever is missing (venv + deps, frontend standalone build,
redis on :6379) and then runs the **same entrypoint** the Docker image uses
(migrations → API → worker + beat → frontend on :3000). Open
http://localhost:3000. Ctrl-C stops everything.

## Manual / hot-reload development


## 0. Prereqs

- Python 3.11+ (3.12 used), Node 18+ (20 used), git
- Redis (`redis-server` or brew/homebrew service) on `:6379`

## 1. Backend

```bash
cd LeadSynt
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements-dev.txt
cd backend
cp ../.env.example .env          # then set a long LEADSynt_SECRET_KEY
mkdir -p ../database/dev         # SQLite needs the directory to exist

.venv/bin/alembic upgrade head   # creates database/dev/leadsynt_dev.db
.venv/bin/uvicorn app.main:app --port 8000 --reload
# startup lifespan seeds roles/users/agents/settings/connectors
```

API live at http://localhost:8000 — `/docs` for OpenAPI.

## 2. Seed the real pipeline data

```bash
# in a second shell (API running), as admin:
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@leadsynt.io","password":"LeadSynt-Dev-Only-2026"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

curl -s -X POST localhost:8000/api/v1/sources/dev_feed/run -H "Authorization: Bearer $TOKEN"
```

## 3. Worker + beat (optional for on-demand work; required for schedules)

```bash
.venv/bin/celery -A app.workers.celery_app:celery worker --loglevel=info
.venv/bin/celery -A app.workers.celery_app:celery beat --loglevel=info
```

## 4. Frontend

```bash
cd LeadSynt/frontend
npm install
npm run dev        # http://localhost:3000 — /api/* proxies to :8000
```

Production build: `npm run build && npm run start`.

## 5. Verify

```bash
backend/.venv/bin/python ../tests/e2e/foundation_check.py   # 24 checks
cd backend && .venv/bin/pytest app/tests -q                  # 70 tests
```

## Key environment variables (backend/.env)

All prefixed `LEADSynt_`. See `.env.example` for the full list with comments.
The dev profile uses `sqlite:////absolute/path/database/dev/leadsynt_dev.db`.
Production targets `mssql+pyodbc://...` (see operations/docker.md).
