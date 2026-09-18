"""Conversations & messages — supports the reply-handover dossier.

Kept deliberately minimal in the foundation; the full conversations/replies
modules extend these tables later.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IDMixin, TimestampMixin


class Conversation(IDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("ticket_id", "contact_id"),)

    ticket_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tickets.id", ondelete="CASCADE"), index=True, nullable=False
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[str] = mapped_column(String(32), default="email", nullable=False)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    messages: Mapped[list["ConversationMessage"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at"
    )


class ConversationMessage(IDMixin, TimestampMixin, Base):
    __tablename__ = "conversation_messages"

    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    direction: Mapped[str] = mapped_column(String(12), nullable=False)  # incoming | outgoing
    sender: Mapped[str | None] = mapped_column(String(320), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, default=None, nullable=True)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
