"""Sources & connectors — the compliance-first discovery layer.

Connectors only pull from authorized channels (official APIs, permitted
public pages, feeds, licensed datasets, user-authorized integrations).
No CAPTCHA / paywall / anti-bot bypasses. Every run is recorded.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin, json_mapped
from app.models.enums import AuthMethod, ConnectorHealth, JobStatus, SourceKind


class Source(IDMixin, TimestampMixin, Base):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(200), unique=True, index=True, nullable=False)
    platform: Mapped[str | None] = mapped_column(String(120), nullable=True)
    kind: Mapped[SourceKind] = mapped_column(
        Enum(SourceKind, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=SourceKind.MANUAL, nullable=False,
    )
    base_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    compliance_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class SourceConnector(IDMixin, TimestampMixin, Base):
    __tablename__ = "source_connectors"

    connector_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True, nullable=False)
    auth_method: Mapped[AuthMethod] = mapped_column(
        Enum(AuthMethod, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=AuthMethod.NONE, nullable=False,
    )
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    rate_limit_per_hour: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    health: Mapped[ConnectorHealth] = mapped_column(
        Enum(ConnectorHealth, native_enum=False, length=12, values_callable=lambda e: [m.value for m in e]),
        default=ConnectorHealth.UNKNOWN, nullable=False,
    )
    configuration: Mapped[dict] = json_mapped(default=dict)

    source: Mapped["Source"] = relationship(lazy="joined")
    runs: Mapped[list["ConnectorRun"]] = relationship(
        back_populates="connector", cascade="all, delete-orphan"
    )


class SourceRecord(IDMixin, TimestampMixin, Base):
    """Raw record captured by a connector run (audit-grade provenance)."""

    __tablename__ = "source_records"

    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    connector_run_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payload: Mapped[dict] = json_mapped(default=dict)
    is_consumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ConnectorRun(IDMixin, TimestampMixin, Base):
    __tablename__ = "connector_runs"

    connector_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_connectors.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=12, values_callable=lambda e: [m.value for m in e]),
        default=JobStatus.PENDING, nullable=False, index=True,
    )
    trigger: Mapped[str] = mapped_column(String(32), default="manual", nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tickets_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = json_mapped(default=dict)

    connector: Mapped["SourceConnector"] = relationship(back_populates="runs")


class TicketSource(IDMixin, Base):
    """Provenance link: which source(s) support this ticket."""

    __tablename__ = "ticket_sources"

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), index=True, nullable=True
    )
    source_record_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ticket: Mapped["Ticket"] = relationship(back_populates="ticket_sources")
