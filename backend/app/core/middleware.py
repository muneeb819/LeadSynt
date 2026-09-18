"""HTTP middlewares: request id, access log, CORS-friendly security headers,
and a simple per-IP sliding-window rate limiter (stateless-safe for dev;
front it with a gateway limit in production)."""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import get_settings

logger = logging.getLogger("leadsynt.http")

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Assign a request id, time the request, emit an access log line."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cache-Control", "no-store")
        path = request.url.path
        if path.startswith("/api"):
            logger.info(
                "%s %s -> %s (%s ms)",
                request.method, path, response.status_code, duration_ms,
                extra={"request_id": request_id, "path": path,
                       "method": request.method, "duration_ms": duration_ms},
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding window per client IP. Dev/foundation-grade; a real
    deployment should enforce limits at the API gateway too."""

    def __init__(self, app, requests_per_minute: int) -> None:
        super().__init__(app)
        self.limit = requests_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api"):
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        window = self._hits[ip]
        while window and now - window[0] > 60:
            window.popleft()
        if len(window) >= self.limit:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many requests. Retry later.",
                        "details": {"retry_after_seconds": 60},
                        "request_id": getattr(request.state, "request_id", None),
                    }
                },
            )
        window.append(now)
        return await call_next(request)


def install_middlewares(app) -> None:
    s = get_settings()
    app.add_middleware(RateLimitMiddleware, requests_per_minute=s.rate_limit_requests_per_minute)
    app.add_middleware(RequestContextMiddleware)
