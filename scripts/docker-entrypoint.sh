#!/usr/bin/env bash
# LeadSynt — single-image entrypoint.
# Runs the WHOLE platform from one container:
#   1. alembic upgrade head          (schema is always current before boot)
#   2. FastAPI on loopback:8000      (never exposed to the network)
#   3. Celery worker + beat          (jobs & schedules)
#   4. Next.js standalone on :3000   (the ONLY public port; proxies /api/*)
#
# Paths/env are overridable so the same script also runs the local dev
# stack (see scripts/dev_up.sh).
set -euo pipefail

APP_ROOT="${LEADSynt_APP_ROOT:-/app}"
BACKEND_DIR="${LEADSynt_BACKEND_DIR:-$APP_ROOT/backend}"
FRONTEND_DIR="${LEADSynt_FRONTEND_DIR:-$APP_ROOT/frontend}"
PYBIN="${LEADSynt_PYBIN:-/usr/local/bin}"
API_HOST="${LEADSynt_API_BIND:-127.0.0.1}"
API_PORT="${LEADSynt_API_PORT:-8000}"
WEB_PORT="${LEADSynt_WEB_PORT:-3000}"

log() { echo "[leadsynt] $*"; }

log "migrating database (alembic upgrade head) ..."
cd "$BACKEND_DIR"
"$PYBIN/alembic" upgrade head

log "starting API on ${API_HOST}:${API_PORT} (loopback-only) ..."
"$PYBIN/uvicorn" app.main:app --host "$API_HOST" --port "$API_PORT" &
API_PID=$!

# Wait for readiness before wiring the frontend in front of it
"$PYBIN/python" - "$API_PORT" <<'PY'
import sys, time, urllib.request
port = sys.argv[1]
for _ in range(60):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/v1/health/ready", timeout=2) as r:
            if r.status == 200:
                print(f"[leadsynt] API ready on 127.0.0.1:{port}")
                sys.exit(0)
    except Exception:
        time.sleep(1)
print("[leadsynt] ERROR: API did not become ready in 60s", file=sys.stderr)
sys.exit(1)
PY

log "starting celery worker + beat ..."
"$PYBIN/celery" -A app.workers.celery_app:celery worker --loglevel=info --concurrency=2 &
WORKER_PID=$!
"$PYBIN/celery" -A app.workers.celery_app:celery beat --loglevel=info &
BEAT_PID=$!

cleanup() {
  log "shutting down ..."
  kill "$API_PID" "$WORKER_PID" "$BEAT_PID" 2>/dev/null || true
  wait 2>/dev/null || true
}
trap cleanup TERM INT

log "starting frontend on 0.0.0.0:${WEB_PORT} (single public origin) ..."
cd "$FRONTEND_DIR"
HOSTNAME=0.0.0.0 PORT="$WEB_PORT" exec node server.js
