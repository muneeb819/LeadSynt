"""Email channel adapter: ``log`` transport (default, deterministic) + SMTP.

- ``log``: records the attempt to the outbound log; returns queued=True with
  NO claim of external delivery.
- ``smtp``: performs real delivery via stdlib smtplib using the SMTP
  settings; returns delivered=True with the generated Message-ID as the
  provider reference.

Transport failures never raise — they come back as ``DeliveryResult(error=...)
`` so the outreach service records a FAILED message (audited).
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, make_msgid

from app.core.config import get_settings
from app.outreach.base import ChannelAdapter, DeliveryResult, register_adapter

logger = logging.getLogger("leadsynt.outreach.email")


@register_adapter
class EmailAdapter(ChannelAdapter):
    channel = "email"

    def send(self, *, message, contact, ticket) -> DeliveryResult:  # noqa: ANN001
        s = get_settings()
        transport = (message.meta or {}).get("transport") or s.outreach_email_transport
        if transport == "smtp":
            return self._send_smtp(message, contact, s)
        if transport in ("", "log"):
            return DeliveryResult(
                queued=True,
                transport="log",
                note=(
                    "log transport: outbound message recorded, no external delivery "
                    "(set LEADSynt_OUTREACH_EMAIL_TRANSPORT=smtp + SMTP settings to "
                    "enable real delivery)"
                ),
            )
        return DeliveryResult(error=f"unknown email transport: {transport}")

    def _send_smtp(self, message, contact, s) -> DeliveryResult:  # noqa: ANN001
        if not s.email_smtp_host:
            return DeliveryResult(error="smtp transport requires LEADSynt_EMAIL_SMTP_HOST")
        to_email = (contact and contact.work_email) if contact else None
        if not to_email:
            return DeliveryResult(error="no work email on contact; cannot send")

        msg = EmailMessage()
        msg["From"] = formataddr((s.outreach_sender_name or "LeadSynt", s.outreach_email_from))
        msg["To"] = to_email
        msg["Subject"] = message.subject
        msg["Message-ID"] = make_msgid()
        msg["Date"] = format_datetime(datetime.now(timezone.utc))
        msg.set_content(message.body)
        message_id = msg["Message-ID"]

        try:
            with smtplib.SMTP(s.email_smtp_host, s.email_smtp_port, timeout=30) as server:
                if s.email_smtp_port == 587:
                    server.starttls()
                server.send_message(msg)
        except Exception as exc:  # noqa: BLE001 — transport failure is a result, not a crash
            logger.warning("smtp send failed: %s", exc)
            return DeliveryResult(error=f"smtp send failed: {exc.__class__.__name__}: {exc}")
        return DeliveryResult(delivered=True, transport="smtp", provider_ref=message_id)