"""Operations & governance: audit, jobs, webhooks, notifications, settings,
suppression, consent, change control."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin, json_mapped
from app.models.enums import (
    ChangeRequestStatus, ConsentStatus, JobStatus, NotificationChannel,
    NotificationType,
)


class AuditLog(IDMixin, Base):
    __tablename__ = "audit_logs"

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    actor_type: Mapped[str] = mapped_column(String(32), default="system", nullable=False)  # user|agent|system|webhook
    action: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[dict | None] = json_mapped(default=dict)
    after: Mapped[dict | None] = json_mapped(default=dict)
    meta: Mapped[dict | None] = json_mapped(default=dict)


class Job(IDMixin, TimestampMixin, Base):
    __tablename__ = "jobs"

    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class JobRun(IDMixin, TimestampMixin, Base):
    __tablename__ = "job_runs"

    job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=12, values_callable=lambda e: [m.value for m in e]),
        default=JobStatus.PENDING, nullable=False, index=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    result: Mapped[dict | None] = json_mapped(default=dict)


class WebhookEvent(IDMixin, TimestampMixin, Base):
    __tablename__ = "webhook_events"

    source: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    payload: Mapped[dict] = json_mapped(default=dict)
    signature_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="RECEIVED", index=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Notification(IDMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel, native_enum=False, length=10, values_callable=lambda e: [m.value for m in e]),
        default=NotificationChannel.IN_APP, nullable=False,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=NotificationType.SYSTEM, nullable=False,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    ticket_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SystemSetting(IDMixin, TimestampMixin, Base):
    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    value: Mapped[dict | None] = json_mapped(default=dict)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class SuppressionRecord(IDMixin, TimestampMixin, Base):
    """DO-NOT-CONTACT / opt-out. Checked before any outreach (business rule)."""

    __tablename__ = "suppression_records"

    scope: Mapped[str] = mapped_column(String(32), nullable=False)  # email | phone | contact | company
    value: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    contact_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConsentRecord(IDMixin, TimestampMixin, Base):
    __tablename__ = "consent_records"

    contact_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    purpose: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus, native_enum=False, length=12, values_callable=lambda e: [m.value for m in e]),
        default=ConsentStatus.GRANTED, nullable=False,
    )
    source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChangeRequest(IDMixin, TimestampMixin, Base):
    """Change-control pipeline for AI-assisted code/config/DB changes:
    USER REQUEST → QA MASTER → CHANGE PLAN → IMPACT → VALIDATION → APPROVAL
    → APPLY → TESTS → QA → DEPLOY → POST-CHECK → ROLLBACK IF NECESSARY."""

    __tablename__ = "change_requests"

    kind: Mapped[str] = mapped_column(String(32), nullable=False)  # code | config | database | deploy
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    plan: Mapped[dict | None] = json_mapped(default=dict)
    impact_analysis: Mapped[dict | None] = json_mapped(default=dict)
    status: Mapped[ChangeRequestStatus] = mapped_column(
        Enum(ChangeRequestStatus, native_enum=False, length=14, values_callable=lambda e: [m.value for m in e]),
        default=ChangeRequestStatus.PROPOSED, nullable=False, index=True,
    )
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rollback_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
