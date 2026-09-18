"""Verification records — history is stored, never overwritten.

Foundation implementations are deterministic (syntax/MX-less heuristics,
disposable-domain list, phone format). Provider integrations (MX lookup,
carrier lookup, etc.) plug in later behind the same record shapes.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin, json_mapped
from app.models.enums import VerificationKind, VerificationResult


class VerificationRecord(IDMixin, TimestampMixin, Base):
    __tablename__ = "verification_records"

    entity_kind: Mapped[VerificationKind] = mapped_column(
        Enum(VerificationKind, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False, index=True,
    )
    entity_ref: Mapped[str] = mapped_column(String(320), index=True, nullable=False)  # ticket/contact/company id
    kind: Mapped[VerificationKind] = mapped_column(
        Enum(VerificationKind, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    result: Mapped[VerificationResult] = mapped_column(
        Enum(VerificationResult, native_enum=False, length=14, values_callable=lambda e: [m.value for m in e]),
        nullable=False, index=True,
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(120), nullable=True)  # user id or agent id
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    evidence: Mapped[dict | None] = json_mapped(default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class EmailVerification(IDMixin, TimestampMixin, Base):
    __tablename__ = "email_verifications"

    record_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    syntax_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mx_present: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_disposable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_catch_all: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = json_mapped(default=dict)


class PhoneVerification(IDMixin, TimestampMixin, Base):
    __tablename__ = "phone_verifications"

    record_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    is_valid_format: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    country: Mapped[str | None] = mapped_column(String(8), nullable=True)
    carrier: Mapped[str | None] = mapped_column(String(120), nullable=True)
    line_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict | None] = json_mapped(default=dict)


class IdentityVerification(IDMixin, TimestampMixin, Base):
    __tablename__ = "identity_verifications"

    record_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    contact_ref: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    profile_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    company_website_match: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    public_source_consistency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    details: Mapped[dict | None] = json_mapped(default=dict)
