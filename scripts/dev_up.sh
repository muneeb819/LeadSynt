#!/usr/bin/env bash
# LeadSynt — one-shot local run, no Docker needed.
# Prepares the environment (venv, npm build, redis) then hands off to the
# SAME entrypoint the container uses, so local and deployed behavior match.
#
#   ./scripts/dev_up.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
VENV="$BACKEND/.venv"

say() { echo "[dev_up] $*"; }

# 1. python venv + deps
if [ ! -x "$VENV/bin/python" ]; then
  say "creating python venv + installing backend deps ..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r "$BACKEND/requirements-dev.txt"
fi

# 2. frontend production build (standalone)
if [ ! -f "$FRONTEND/.next/standalone/server.js" ]; then
  say "installing frontend deps + building (standalone) ..."
  (cd "$FRONTEND" && npm install --no-audit --no-fund)
  (cd "$FRONTEND" && NEXT_TELEMETRY_DISABLED=1 npm run build)
fi

# the standalone server expects its static assets next to server.js
if [ ! -d "$FRONTEND/.next/standalone/.next/static" ]; then
  mkdir -p "$FRONTEND/.next/standalone/.next"
  cp -r "$FRONTEND/.next/static" "$FRONTEND/.next/standalone/.next/static"
fi

# public assets (branding, etc.)
if [ -d "$FRONTEND/public" ]; then
  cp -r "$FRONTEND/public" "$FRONTEND/.next/standalone/public"
fi

# 3. redis on :6379 (system redis if present, else the static binary
#    bundled with the `redislite` package, else fail with a hint)
if ! (redis-cli -p 6379 ping >/dev/null 2>&1 || \
      "$VENV/bin/python" -c "import redis; redis.Redis(port=6379).ping()" >/dev/null 2>&1); then
  say "starting redis on :6379 ..."
  if command -v redis-server >/dev/null 2>&1; then
    redis-server --port 6379 --bind 127.0.0.1 --daemonize yes
  else
    BIN="$("$VENV/bin/python" -c "import redislite; print(redislite.__redis_executable__)" 2>/dev/null || true)"
    if [ -n "$BIN" ] && [ -x "$BIN" ]; then
      "$BIN" --port 6379 --bind 127.0.0.1 --daemonize yes --logfile /tmp/leadsynt-redis.log
    else
      say "ERROR: no redis available — install redis, or: $VENV/bin/pip install redislite"
      exit 1
    fi
  fi
  sleep 1
fi

# 4. database file (SQLite dev profile)
mkdir -p "$ROOT/database/dev"

# 5. the same entrypoint the container runs
exec env \
  LEADSynt_APP_ROOT="$ROOT" \
  LEADSynt_BACKEND_DIR="$BACKEND" \
  LEADSynt_FRONTEND_DIR="$FRONTEND/.next/standalone" \
  LEADSynt_PYBIN="$VENV/bin" \
  LEADSynt_API_BIND=127.0.0.1 \
  LEADSynt_WEB_PORT=3000 \
  "$ROOT/scripts/docker-entrypoint.sh"
