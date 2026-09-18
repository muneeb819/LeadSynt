"""Health endpoints (public)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import __version__
from app.api.deps import get_db
from app.core.config import get_settings
from app.schemas.common import HealthOut

router = APIRouter()


def _check(name: str, fn) -> str:
    try:
        fn()
        return "ok"
    except Exception as exc:  # noqa: BLE001
        return f"error: {exc.__class__.__name__}"


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)):
    s = get_settings()
    return HealthOut(
        status="ok",
        version=__version__,
        environment=s.environment,
        checks={
            "database": _check("db", lambda: db.execute(text("SELECT 1"))),
            "redis": _check(
                "redis",
                lambda: __import__("redis").Redis.from_url(s.redis_url, socket_connect_timeout=1).ping(),
            ),
        },
    )


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    """Readiness: database must be up."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:  # noqa: BLE001
        return {"status": "not_ready"}
