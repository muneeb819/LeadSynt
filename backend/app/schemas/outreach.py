"""Schemas for the Outreach API (Phase B)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OutreachTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    channel: str = "email"
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1)
    description: str | None = None
    is_active: bool = True


class OutreachMessageCreate(BaseModel):
    ticket_id: str
    contact_id: str | None = None
    template_id: str | None = None
    template_name: str | None = None
    channel: str = "email"
    subject: str | None = None
    body: str | None = None
    sequence: int = Field(default=1, ge=1)
    scheduled_for: datetime | None = None


class FollowUpRuleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    channel: str = "email"
    sequence: int = Field(default=2, ge=2)
    delay_hours: int = Field(default=48, ge=1)
    max_follow_ups: int = Field(default=2, ge=1)
    requires_human_authorization: bool = True
    is_active: bool = True
    description: str | None = None


class FollowUpAuthorizeIn(BaseModel):
    ticket_id: str
    max_follow_ups: int = Field(default=2, ge=1)
    notes: str | None = None