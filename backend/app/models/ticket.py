"""The Ticket — LeadSynt's central business object.

A Ticket represents any legitimate business opportunity / requirement / lead
/ buyer / seller / job / client request / RFP discovered from an authorized
source. Identity, strategic context, provenance, intelligence and CRM state
all live here; related entities (contacts, companies, sources, verification,
scoring) are attached through association tables with full provenance.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric,
    String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin, json_mapped
from app.models.enums import (
    DuplicateStatus, Freshness, IntentLevel, TicketStatus, VerificationStatus,
)


class TicketType(IDMixin, TimestampMixin, Base):
    __tablename__ = "ticket_types"

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


class TicketStatus(IDMixin, TimestampMixin, Base):
    """Status registry rows (config-driven); the *state machine* rules live
    in ``app.services.ticket_status_machine``."""

    __tablename__ = "ticket_statuses"

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class TicketCategory(IDMixin, TimestampMixin, Base):
    __tablename__ = "ticket_categories"

    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    marketplace_domain: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Ticket(IDMixin, TimestampMixin, Base):
    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint("lead_score BETWEEN 0 AND 100", name="lead_score_range"),
        CheckConstraint("intent_score BETWEEN 0 AND 100", name="intent_score_range"),
        CheckConstraint("risk_score BETWEEN 0 AND 100", name="risk_score_range"),
    )

    # -- Identity ------------------------------------------------------------
    reference: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    type_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ticket_types.id"), index=True, nullable=False
    )
    status_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ticket_statuses.id"), index=True, nullable=False
    )
    category_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("ticket_categories.id"), index=True, nullable=True
    )
    domain: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    market_sector: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    product: Mapped[str | None] = mapped_column(String(200), nullable=True)
    service: Mapped[str | None] = mapped_column(String(200), nullable=True)
    requirement: Mapped[str | None] = mapped_column(Text, nullable=True)
    requirement_details: Mapped[dict | None] = json_mapped(default=dict)

    # -- Strategic context ------------------------------------------------------
    intent_level: Mapped[IntentLevel | None] = mapped_column(
        Enum(IntentLevel, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e]),
        nullable=True,
    )
    urgency: Mapped[str | None] = mapped_column(String(32), nullable=True)
    budget: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    deal_size: Mapped[str | None] = mapped_column(String(32), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), index=True, nullable=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pain_point: Mapped[str | None] = mapped_column(Text, nullable=True)

    # -- Provenance (mandatory) -------------------------------------------------
    platform: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    platform_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    original_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    official_website_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discovered_by: Mapped[str | None] = mapped_column(String(200), nullable=True)  # connector/agent id or user

    # -- Intelligence -------------------------------------------------------------
    lead_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    intent_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, native_enum=False, length=16, values_callable=lambda e: [m.value for m in e]),
        default=VerificationStatus.UNVERIFIED, nullable=False, index=True,
    )
    freshness: Mapped[Freshness] = mapped_column(
        Enum(Freshness, native_enum=False, length=12, values_callable=lambda e: [m.value for m in e]),
        default=Freshness.FRESH, nullable=False,
    )
    duplicate_status: Mapped[DuplicateStatus] = mapped_column(
        Enum(DuplicateStatus, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=DuplicateStatus.UNIQUE, nullable=False, index=True,
    )

    # -- CRM -----------------------------------------------------------------------
    owner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), index=True, nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # -- Relationships (read-model sugar; associations are the source of truth) --
    type: Mapped["TicketType"] = relationship(lazy="joined")
    status: Mapped["TicketStatus"] = relationship(lazy="joined")
    category: Mapped["TicketCategory"] = relationship(lazy="joined")
    owner: Mapped["User | None"] = relationship(lazy="noload")
    ticket_sources: Mapped[list["TicketSource"]] = relationship(
        "TicketSource", back_populates="ticket", cascade="all, delete-orphan"
    )
    ticket_contacts: Mapped[list["TicketContact"]] = relationship(
        "TicketContact", back_populates="ticket", cascade="all, delete-orphan"
    )
    ticket_companies: Mapped[list["TicketCompany"]] = relationship(
        "TicketCompany", back_populates="ticket", cascade="all, delete-orphan"
    )
