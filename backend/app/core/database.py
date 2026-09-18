"""Database session layer.

The application is *designed for Microsoft SQL Server*. SQLAlchemy provides
the dialect boundary: the production URL is ``mssql+pyodbc://...`` and the
local dev profile may use SQLite. No frontend or connector ever talks to the
database directly — only this module, via ``get_db``.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

_META = MetaData(naming_convention={
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
})


class Base(DeclarativeBase):
    """Declarative base; constraint names follow SQL Server conventions."""

    metadata = _META


def build_engine(url: str | None = None, echo: bool | None = None) -> Engine:
    s = get_settings()
    url = url or s.database_url
    echo = s.db_echo if echo is None else echo
    kwargs: dict = {"echo": echo, "future": True}
    if url.startswith("sqlite"):
        # SQLite: allow cross-connection access for test/dev ergonomics.
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in ("sqlite://", "sqlite:///:memory:"):
            kwargs["poolclass"] = StaticPool
    else:
        kwargs.update(
            pool_size=s.db_pool_size,
            max_overflow=s.db_max_overflow,
            pool_recycle=s.db_pool_recycle_seconds,
            pool_pre_ping=True,
        )
    return create_engine(url, **kwargs)


engine: Engine = build_engine()
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: one session per request, always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_engine(url: str) -> None:
    """Replace the module engine (used by tests to point at a test database)."""
    global engine, SessionLocal
    engine.dispose()
    engine = build_engine(url)
    SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False, autoflush=False)
