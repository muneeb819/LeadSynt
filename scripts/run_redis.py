"""Embedded Redis for the sandbox dev environment.

The sandbox has no system redis and no root; `redislite` (in backend/.venv)
bundles a static redis-server binary we run directly on :6379 for Celery +
rate limiting. In Docker/prod the compose `redis:7-alpine` service is used
instead (see docker-compose.yml).

Usage:
  backend/.venv/bin/python scripts/run_redis.py
"""
import subprocess
import sys

sys.path.insert(0, "/home/user/LeadSynt/backend")
import redislite  # noqa: E402  (only for the bundled binary path)

BIN = redislite.__redis_executable__
subprocess.run([BIN, "--port", "6379", "--bind", "127.0.0.1"], check=True)
