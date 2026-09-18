"""Shared API schema primitives."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Envelope(BaseModel):
    """Standard success envelope: data + request_id."""

    data: Any
    request_id: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any | None = None
    request_id: str | None = None


class Page(BaseModel):
    items: list[Any]
    pagination: dict[str, Any]


class HealthOut(BaseModel):
    status: str
    version: str
    environment: str
    checks: dict[str, str]
