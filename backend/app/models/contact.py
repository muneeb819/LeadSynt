"""Contacts and their value objects (emails, phones, profiles)."""

from __future__ import annotations

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin
from app.models.enums import TicketContactRole


class Contact(IDMixin, TimestampMixin, Base):
    __tablename__ = "contacts"

    full_name: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    work_email: Mapped[str | None] = mapped_column(String(320), index=True, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    profile_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), index=True, nullable=True
    )
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    locale: Mapped[str | None] = mapped_column(String(32), nullable=True)

    emails: Mapped[list["ContactEmail"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )
    phones: Mapped[list["ContactPhone"]] = relationship(
        back_populates="contact", cascade="all, delete-orphan"
    )
    company: Mapped["Company | None"] = relationship(lazy="noload")


class ContactEmail(IDMixin, TimestampMixin, Base):
    __tablename__ = "contact_emails"

    contact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(40), default="work", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    contact: Mapped["Contact"] = relationship(back_populates="emails")


class ContactPhone(IDMixin, TimestampMixin, Base):
    __tablename__ = "contact_phones"

    contact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    phone: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(40), default="mobile", nullable=False)
    country_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    contact: Mapped["Contact"] = relationship(back_populates="phones")


class TicketContact(IDMixin, Base):
    __tablename__ = "ticket_contacts"

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    contact_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[TicketContactRole] = mapped_column(
        Enum(TicketContactRole, native_enum=False, length=20, values_callable=lambda e: [m.value for m in e]),
        default=TicketContactRole.PRIMARY, nullable=False,
    )

    ticket: Mapped["Ticket"] = relationship(back_populates="ticket_contacts")
    contact: Mapped["Contact"] = relationship(lazy="joined")
