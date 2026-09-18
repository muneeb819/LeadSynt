"""QA Master data model: runs, findings, reports."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin, json_mapped
from app.models.enums import FindingSeverity, FindingStatus, QATrigger


class QARun(IDMixin, TimestampMixin, Base):
    __tablename__ = "qa_runs"

    trigger: Mapped[QATrigger] = mapped_column(
        Enum(QATrigger, native_enum=False, length=12, values_callable=lambda e: [m.value for m in e]),
        default=QATrigger.MANUAL, nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="RUNNING", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict | None] = json_mapped(default=dict)


class QAFinding(IDMixin, TimestampMixin, Base):
    __tablename__ = "qa_findings"

    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    category: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[FindingSeverity] = mapped_column(
        Enum(FindingSeverity, native_enum=False, length=10, values_callable=lambda e: [m.value for m in e]),
        nullable=False, index=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence: Mapped[dict | None] = json_mapped(default=dict)
    root_cause_hypothesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    affected_component: Mapped[str | None] = mapped_column(String(120), nullable=True)
    test_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[FindingStatus] = mapped_column(
        Enum(FindingStatus, native_enum=False, length=14, values_callable=lambda e: [m.value for m in e]),
        default=FindingStatus.OPEN, nullable=False, index=True,
    )


class QAReport(IDMixin, TimestampMixin, Base):
    __tablename__ = "qa_reports"

    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
