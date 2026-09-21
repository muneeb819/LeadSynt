"""Outreach engine models (Phase B): templates, messages, follow-up rules and
explicit human authorizations.

The reply-handover hard rule still applies: after a qualifying reply,
automated follow-ups NEVER resume on their own — a human must explicitly
authorize them (``OutreachFollowUpAuthorization``), and every authorization
is audited.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin


class OutreachTemplate(IDMixin, TimestampMixin, Base):
    """Library of compliant outreach templates (placeholder-based)."""

    __tablename__ = "outreach_templates"

    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), default="email", nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class OutreachMessage(IDMixin, TimestampMixin, Base):
    """One outbound message (initial contact or follow-up) per ticket/contact.

    Status flow: DRAFT -> SCHEDULED -> SENT (through a channel adapter), with
    terminal FAILED / BLOCKED / CANCELLED states. QUEUED means the message was
    accepted into the outbound log WITHOUT confirmed external delivery (the
    default ``log`` transport — it never claims a delivery that did not
    happen).
    """

    __tablename__ = "outreach_messages"

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="SET NULL"), index=True, nullable=True
    )
    template_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("outreach_templates.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32), default="email", nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # DRAFT | SCHEDULED | QUEUED | SENT | FAILED | BLOCKED | CANCELLED
    status: Mapped[str] = mapped_column(
        String(24), default="DRAFT", index=True, nullable=False
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True, nullable=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    transport: Mapped[str | None] = mapped_column(String(32), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_by: Mapped[str | None] = mapped_column(String(64), nullable=True)  # user or agent id
    meta: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)


class FollowUpRule(IDMixin, TimestampMixin, Base):
    """Cadence rule for a sequence position (e.g. 2nd message 48h later)."""

    __tablename__ = "follow_up_rules"
    __table_args__ = (UniqueConstraint("channel", "sequence"),)

    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    channel: Mapped[str] = mapped_column(String(32), default="email", nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    delay_hours: Mapped[int] = mapped_column(Integer, default=48, nullable=False)
    max_follow_ups: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    requires_human_authorization: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class OutreachFollowUpAuthorization(IDMixin, TimestampMixin, Base):
    """Explicit human authorization to send follow-ups on a ticket after the
    reply-handover pause. Records who authorized, when, and how many follow-up
    messages may be sent (sequence <= max_follow_ups)."""

    __tablename__ = "outreach_follow_up_authorizations"

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"),
        unique=True, index=True, nullable=False,
    )
    authorized_by: Mapped[str] = mapped_column(String(36), nullable=False)
    authorized_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    max_follow_ups: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)