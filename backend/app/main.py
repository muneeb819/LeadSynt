"""LeadSynt backend — FastAPI application factory.

Frontend -> this API -> database. No other path to data exists.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import AppError
from app.core.logging import setup_logging
from app.core.middleware import install_middlewares
from app.core.security import TokenError
from app.monitoring import metrics

logger = logging.getLogger("leadsynt")


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _error_response(status: int, code: str, message: str, details=None, request_id=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details,
                           "request_id": request_id}},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    setup_logging(s.log_level, s.log_json)
    logger.info("LeadSynt backend starting (env=%s, version=%s)", s.environment, __version__)

    # Idempotent foundational seeding (RBAC, agents, settings defaults).
    from app.agents.registry import ensure_agents_seeded
    from app.auth.rbac import ensure_rbac_seeded
    from app.configuration import ensure_defaults
    from app.models.ticket import TicketStatus as TicketStatusRow
    from app.models.enums import TicketStatus
    from sqlalchemy import select

    db = SessionLocal()
    try:
        ensure_rbac_seeded(db)
        ensure_agents_seeded(db)
        ensure_defaults(db)
        have = {r.code for r in db.execute(select(TicketStatusRow)).scalars()}
        for st in TicketStatus:
            if st.value not in have:
                db.add(TicketStatusRow(
                    code=st.value, name=st.value.replace("_", " ").title(),
                    is_terminal=st in {
                        TicketStatus.WON, TicketStatus.LOST, TicketStatus.DISQUALIFIED,
                        TicketStatus.DUPLICATE, TicketStatus.EXPIRED, TicketStatus.ARCHIVED,
                    },
                ))
        db.commit()
        logger.info("foundational seed check complete")
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("startup seed failed — run 'alembic upgrade head' first")
    finally:
        db.close()
    yield
    logger.info("LeadSynt backend stopped")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="LeadSynt API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if not s.is_production else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID",
                       "X-LeadSynt-Signature", "X-LeadSynt-Timestamp", "X-LeadSynt-Source"],
    )
    install_middlewares(app)

    # ---------------- exception handlers (structured errors) ----------------
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        metrics.inc_error(exc.status_code)
        return _error_response(exc.status_code, exc.code, exc.message, exc.details,
                               _request_id(request))

    @app.exception_handler(TokenError)
    async def token_error_handler(request: Request, exc: TokenError):
        metrics.inc_error(401)
        return _error_response(401, "unauthorized", str(exc), None, _request_id(request))

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        metrics.inc_error(422)
        return _error_response(422, "validation_error", "Request validation failed",
                               exc.errors(), _request_id(request))

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException):
        metrics.inc_error(exc.status_code)
        return _error_response(exc.status_code, "http_error",
                               exc.detail if isinstance(exc.detail, str) else "HTTP error",
                               None, _request_id(request))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        metrics.inc_error(500)
        logger.exception("unhandled error")
        # Secure error handling: never leak internals.
        return _error_response(500, "internal_error", "Internal server error", None,
                               _request_id(request))

    # ---------------- routes ----------------
    app.include_router(api_router, prefix=s.api_v1_prefix)
    from app.webhooks.inbox import router as webhook_router

    app.include_router(webhook_router, prefix=f"{s.api_v1_prefix}/webhooks", tags=["webhooks"])

    @app.get("/metrics")
    def metrics_endpoint():
        if not s.metrics_enabled:
            return {"status": "disabled"}
        return metrics.snapshot()

    @app.get("/")
    def root():
        return {"name": "LeadSynt API", "version": __version__, "docs": "/docs",
                "health": f"{s.api_v1_prefix}/health"}

    return app


app = create_app()
