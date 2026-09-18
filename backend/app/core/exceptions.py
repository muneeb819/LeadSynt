"""Structured errors.

Every API error has a stable machine-readable ``code``, a human message,
optional details, and the request id — so clients can react deterministically
and logs stay auditable.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: Any = None, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code is not None:
            self.code = code


class BadRequestError(AppError):
    status_code = 400
    code = "bad_request"


class ValidationAppError(AppError):
    status_code = 422
    code = "validation_error"


class UnauthorizedError(AppError):
    status_code = 401
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = 403
    code = "forbidden"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"


class StatusTransitionError(ConflictError):
    """Raised by the Ticket status machine when a transition is illegal."""

    code = "invalid_status_transition"


class SuppressedContactError(ForbiddenError):
    """Raised when outreach targets a suppressed / DO-NOT-CONTACT record."""

    code = "suppressed_contact"
