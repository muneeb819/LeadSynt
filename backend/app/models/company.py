"""Companies and their domains."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin
from app.models.enums import TicketCompanyRole


class Company(IDMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    legal_name: Mapped[str] = mapped_column(String(300), index=True, nullable=False)
    trade_name: Mapped[str | None] = mapped_column(String(300), nullable=True)
    website: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    size_band: Mapped[str | None] = mapped_column(String(32), nullable=True)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    domains: Mapped[list["CompanyDomain"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class CompanyDomain(IDMixin, TimestampMixin, Base):
    __tablename__ = "company_domains"

    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    domain: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_official_website: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    company: Mapped["Company"] = relationship(back_populates="domains")


class TicketCompany(IDMixin, Base):
    __tablename__ = "ticket_companies"

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    company_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[TicketCompanyRole] = mapped_column(
        Enum(TicketCompanyRole, native_enum=False, length=12, values_callable=lambda e: [m.value for m in e]),
        default=TicketCompanyRole.PRIMARY, nullable=False,
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="ticket_companies")
    company: Mapped["Company"] = relationship(lazy="joined")
