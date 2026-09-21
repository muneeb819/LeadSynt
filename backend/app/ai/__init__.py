"""AI infrastructure (Phase A): provider/model catalog + LLM client.

The catalog tables were added in the Phase A migration; rows are seeded
idempotently at startup by :func:`ensure_ai_catalog_seeded`. Agents consume
LLM capability through :mod:`app.ai.llm` and always have a deterministic
fallback so the platform works (and stays testable) with no API key.
"""