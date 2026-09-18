"""Shared model primitives: id generation, timestamps, JSON columns."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


def new_uuid() -> str:
    return uuid.uuid4().hex


class IDMixin:
    """Portable string UUID primary key (works on SQL Server and SQLite)."""

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=new_uuid
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        nullable=False,
    )


class JSONColumn:
    """JSON column that stays portable (JSONB-equivalent semantics)."""

    @staticmethod
    def column(**kwargs):
        return JSON().with_variant(kwargs.pop("mssql", None), "mssql") if kwargs else JSON()


def json_mapped(default=None):
    return mapped_column(JSON, default=default, nullable=False)
