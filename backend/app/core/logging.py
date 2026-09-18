"""Logging setup: console-friendly or JSON lines, with request context."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("request_id", "user_id", "path", "method", "duration_ms"):
            val = getattr(record, key, None)
            if val is not None:
                payload[key] = val
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", as_json: bool = True) -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter() if as_json else logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    ))
    root.addHandler(handler)
    # Keep noisy third-party loggers at sane levels.
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "celery"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
