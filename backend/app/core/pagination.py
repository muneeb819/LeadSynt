"""Pagination helpers: page-based and cursor-based (token = offset base64).

High-volume lists prefer cursors; page mode is kept for UI ergonomics.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass

from fastapi import Query


@dataclass(frozen=True, slots=True)
class PageResult:
    items: list
    page: int
    page_size: int
    total: int
    total_pages: int

    def to_envelope(self) -> dict:
        return {
            "items": self.items,
            "pagination": {
                "page": self.page,
                "page_size": self.page_size,
                "total": self.total,
                "total_pages": self.total_pages,
                "cursor": _encode_cursor(self.page, self.page_size),
            },
        }


@dataclass(frozen=True, slots=True)
class CursorParams:
    cursor: str | None
    limit: int


def _encode_cursor(page: int, page_size: int) -> str:
    raw = json.dumps({"p": page, "s": page_size}).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode_cursor(cursor: str) -> tuple[int, int]:
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return int(data["p"]), int(data["s"])
    except Exception as exc:  # noqa: BLE001
        from app.core.exceptions import BadRequestError

        raise BadRequestError("Invalid pagination cursor") from exc


def page_params(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
) -> tuple[int, int]:
    return page, page_size


def cursor_params(
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=500),
) -> CursorParams:
    return CursorParams(cursor=cursor, limit=limit)
