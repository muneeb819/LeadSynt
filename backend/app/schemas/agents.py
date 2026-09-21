"""Schemas for the AI agents API (Phase A)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AgentRunRequest(BaseModel):
    """POST /agents/{agent_id}/run body."""

    ticket_id: str | None = Field(default=None, description="Ticket to run the agent against")
    payload: dict[str, Any] | None = Field(
        default=None,
        description="Free-form agent payload (merged over ticket_id)",
    )


class AgentRunOut(BaseModel):
    id: str
    status: str
    kind: str | None = None
    ticket_id: str | None = None
    confidence: float | None = None
    cost_usd: float | None = None
    error: str | None = None
    output: dict[str, Any] | None = None
    started_at: str | None = None
    finished_at: str | None = None