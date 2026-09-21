"""Outreach channel adapters — the transport layer behind outreach_messages.

An adapter turns a persisted :class:`OutreachMessage` into a delivery attempt
on a specific channel. Adapters are honest by construction: they never claim
a message was delivered unless the transport confirmed it. The default
``log`` transport records the attempt to the outbound log (status QUEUED)
without claiming external delivery; the SMTP transport sends real email when
configured (``LEADSynt_OUTREACH_EMAIL_TRANSPORT=smtp`` + SMTP settings).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestError


@dataclass(slots=True)
class DeliveryResult:
    """Outcome of a channel adapter attempt. Exactly one of ``delivered`` /
    ``queued`` / ``error`` describes the attempt."""

    delivered: bool = False
    queued: bool = False
    provider_ref: str | None = None
    transport: str | None = None
    note: str | None = None
    error: str | None = None


class ChannelAdapter(ABC):
    """Base class for all outreach channel adapters."""

    channel: str = "email"

    def __init__(self, db: Session) -> None:
        self.db = db

    @abstractmethod
    def send(
        self, *, message: Any, contact: Any, ticket: Any
    ) -> DeliveryResult:
        """Attempt delivery of ``message``. Must never throw for transport
        failures — return ``DeliveryResult(error=...)`` instead."""


ADAPTERS: dict[str, type[ChannelAdapter]] = {}


def register_adapter(cls: type[ChannelAdapter]) -> type[ChannelAdapter]:
    ADAPTERS[cls.channel] = cls
    return cls


def get_channel_adapter(db: Session, channel: str) -> ChannelAdapter:
    """Resolve the adapter for a channel. Importing the email module registers
    it; additional channels register themselves in the same way."""
    from app.outreach import email as _email_module  # noqa: F401  (registration side effect)

    cls = ADAPTERS.get((channel or "").lower())
    if cls is None:
        raise BadRequestError(
            f"Unsupported outreach channel: {channel}",
            details={"channel": channel, "supported": sorted(ADAPTERS)},
        )
    return cls(db)