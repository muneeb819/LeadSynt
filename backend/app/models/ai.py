"""AI agent registry, runs, decisions and evidence.

Every agent has a unique id, version, purpose, system instructions, allowed
tools, input/output schemas, confidence + evidence requirements, cost and
error tracking, and a full audit trail via ai_runs / ai_evidence.
AI never silently mutates business data — mutations go through services and
are audited.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin, json_mapped
from app.models.enums import AgentStatus, RunStatus


class AIAgent(IDMixin, TimestampMixin, Base):
    __tablename__ = "ai_agents"

    agent_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[str] = mapped_column(String(32), default="1.0.0", nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    system_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    allowed_tools: Mapped[list] = json_mapped(default=list)
    input_schema: Mapped[dict] = json_mapped(default=dict)
    output_schema: Mapped[dict] = json_mapped(default=dict)
    confidence_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AgentStatus] = mapped_column(
        Enum(AgentStatus, native_enum=False, length=12, values_callable=lambda e: [m.value for m in e]),
        default=AgentStatus.ACTIVE, nullable=False,
    )
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    max_cost_usd_per_run: Mapped[float] = mapped_column(Numeric(10, 4), default=0.05, nullable=False)
    # 0.0 = unlimited. Enforced in AgentBase.run (runs are CANCELLED / never
    # charged once the current calendar month's spend reaches the cap).
    monthly_budget_usd: Mapped[float] = mapped_column(Numeric(12, 2), default=0.0, nullable=False)
    total_runs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(14, 6), default=0.0, nullable=False)


class AIRun(IDMixin, TimestampMixin, Base):
    __tablename__ = "ai_runs"

    agent_id: Mapped[str] = mapped_column(
        String(36), index=True, nullable=False
    )  # ai_agents.id
    ticket_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    kind: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False, length=12, values_callable=lambda e: [m.value for m in e]),
        default=RunStatus.PENDING, nullable=False, index=True,
    )
    input: Mapped[dict | None] = json_mapped(default=dict)
    output: Mapped[dict | None] = json_mapped(default=dict)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(10, 6), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIDecision(IDMixin, TimestampMixin, Base):
    __tablename__ = "ai_decisions"

    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    decision: Mapped[str] = mapped_column(String(120), nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class AIEvidence(IDMixin, TimestampMixin, Base):
    __tablename__ = "ai_evidence"

    run_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False)  # url | document | snippet | record
    source_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Numeric(5, 4), default=1.0, nullable=False)


class AIProvider(IDMixin, TimestampMixin, Base):
    """LLM provider catalog row (Phase A). Rows are seeded at startup and
    reference an env var (never a literal key) for the API credential."""

    __tablename__ = "ai_providers"

    provider_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), default="openai_compatible", nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    api_key_env: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class AIModel(IDMixin, TimestampMixin, Base):
    """LLM model catalog row with per-Mtok list price (used for cost
    estimates and budget enforcement even before a key is configured)."""

    __tablename__ = "ai_models"

    model_id: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    provider_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_providers.id", ondelete="CASCADE"), index=True, nullable=False
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    context_window: Mapped[int] = mapped_column(Integer, default=8192, nullable=False)
    input_price_per_mtok: Mapped[float] = mapped_column(Numeric(12, 6), default=0.0, nullable=False)
    output_price_per_mtok: Mapped[float] = mapped_column(Numeric(12, 6), default=0.0, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
