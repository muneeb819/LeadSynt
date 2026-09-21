"""Provider/model catalog: seed data, lookups and config resolution.

Secrets never live here — API keys come from the env var named by
``api_key_env`` (e.g. ``LEADSynt_AI_API_KEY``) at call time.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai import AIModel, AIProvider

# (provider_id, name, kind, base_url, api_key_env, is_default)
DEFAULT_PROVIDERS: list[tuple[str, str, str, str, str | None, bool]] = [
    ("openai", "OpenAI", "openai_compatible", "https://api.openai.com/v1",
     "LEADSynt_AI_API_KEY", True),
    ("anthropic", "Anthropic", "anthropic_messages", "https://api.anthropic.com/v1",
     "LEADSynt_AI_API_KEY", False),
]

# (model_id, provider_id, display_name, context_window, in_price_per_mtok, out_price_per_mtok)
# Prices are approximate public list prices in USD per million tokens, used
# only for cost estimation / budget enforcement.
DEFAULT_MODELS: list[tuple[str, str, str, int, float, float]] = [
    ("gpt-4o-mini", "openai", "GPT-4o mini", 128000, 0.15, 0.60),
    ("gpt-4o", "openai", "GPT-4o", 128000, 2.50, 10.00),
    ("claude-3-5-sonnet-20241022", "anthropic", "Claude 3.5 Sonnet", 200000, 3.00, 15.00),
    ("claude-3-5-haiku-20241022", "anthropic", "Claude 3.5 Haiku", 200000, 0.80, 4.00),
]


def ensure_ai_catalog_seeded(db: Session) -> None:
    """Idempotently seed providers and models (startup + tests)."""
    providers = {p.provider_id: p for p in db.execute(select(AIProvider)).scalars()}
    for pid, name, kind, base_url, key_env, is_default in DEFAULT_PROVIDERS:
        if pid not in providers:
            providers[pid] = AIProvider(
                provider_id=pid, name=name, kind=kind, base_url=base_url,
                api_key_env=key_env, is_default=is_default, enabled=True,
            )
            db.add(providers[pid])
    db.flush()
    models = {m.model_id: m for m in db.execute(select(AIModel)).scalars()}
    for mid, pid, display, ctx, in_price, out_price in DEFAULT_MODELS:
        if mid not in models:
            provider = providers.get(pid)
            if provider is None:
                continue
            models[mid] = AIModel(
                model_id=mid, provider_id=provider.id, display_name=display,
                context_window=ctx, input_price_per_mtok=in_price,
                output_price_per_mtok=out_price, enabled=True,
            )
            db.add(models[mid])
    db.flush()


def get_provider_rows(db: Session) -> list[AIProvider]:
    return list(db.execute(select(AIProvider).order_by(AIProvider.provider_id)).scalars())


def get_model_rows(db: Session) -> list[AIModel]:
    return list(db.execute(select(AIModel).order_by(AIModel.display_name)).scalars())


def get_provider(db: Session, provider_id: str) -> AIProvider | None:
    return db.execute(
        select(AIProvider).where(AIProvider.provider_id == provider_id)
    ).scalar_one_or_none()


def get_model(db: Session, model_id: str) -> AIModel | None:
    return db.execute(
        select(AIModel).where(AIModel.model_id == model_id)
    ).scalar_one_or_none()


def default_model_for(db: Session, provider: AIProvider) -> AIModel | None:
    return db.execute(
        select(AIModel).where(AIModel.provider_id == provider.id, AIModel.enabled == True)
        .order_by(AIModel.input_price_per_mtok.asc()).limit(1)
    ).scalar_one_or_none()


def resolve_llm_config(
    db: Session,
) -> tuple[AIProvider | None, AIModel | None, str | None]:
    """Resolve the configured provider/model/api-key at call time.

    Returns ``(provider, model, api_key)`` — all three ``None`` when AI is
    not configured (``LEADSynt_AI_PROVIDER=none``), so agents fall back to
    their deterministic engines.
    """
    s = get_settings()
    provider_id = (s.ai_provider or "none").strip().lower()
    if provider_id in {"", "none"}:
        return None, None, None
    provider = get_provider(db, provider_id)
    if provider is None or not provider.enabled:
        return None, None, None
    model = get_model(db, s.ai_model) if s.ai_model else None
    if model is None:
        model = default_model_for(db, provider)
    if model is None or not model.enabled:
        return None, None, None
    # The provider catalog names which *env var* holds the credential; the
    # settings instance already exposes it as a pydantic field.
    key = ""
    if provider.api_key_env:
        key = s.ai_api_key or ""
    if not key:
        return provider, model, None
    return provider, model, key