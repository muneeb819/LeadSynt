"""Score snapshots — immutable history of every scoring decision."""

from __future__ import annotations

from sqlalchemy import Enum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin, json_mapped
from app.models.enums import ScoreKind


class _ScoreSnapshotBase(IDMixin, TimestampMixin, Base):
    __abstract__ = True

    kind: Mapped[ScoreKind] = mapped_column(
        Enum(ScoreKind, native_enum=False, length=8, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    ticket_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    factors: Mapped[dict] = json_mapped(default=dict)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # ai_runs.id
    computed_by: Mapped[str] = mapped_column(String(120), default="rule-engine", nullable=False)


class LeadScoreSnapshot(_ScoreSnapshotBase):
    __tablename__ = "lead_score_snapshots"


class IntentScoreSnapshot(_ScoreSnapshotBase):
    __tablename__ = "intent_score_snapshots"


class RiskScoreSnapshot(_ScoreSnapshotBase):
    __tablename__ = "risk_score_snapshots"
