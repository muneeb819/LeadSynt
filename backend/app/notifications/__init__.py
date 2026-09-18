"""Notifications package (re-exports the service)."""

from app.services.notification_service import notify, notify_ticket_owner, unread_count  # noqa: F401
