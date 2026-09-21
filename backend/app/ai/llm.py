"""LLM client + cost estimation (OpenAI-compatible chat completions).

Everything here is optional at runtime: agents call :func:`get_llm_client` and
receive ``None`` when AI is not configured, falling back to their
deterministic engines. Cost is estimated BEFORE the request so the per-run
cap (``AIAgent.max_cost_usd_per_run``) can be enforced without spending
anything.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.ai.catalog import resolve_llm_config
from app.core.config import get_settings
from app.models.ai import AIModel, AIProvider


class LLMError(Exception):
    """Base class for LLM layer failures."""


class LLMUnavailableError(LLMError):
    """The provider/model/key is not usable right now."""


class CostLimitExceededError(LLMError):
    """Estimated cost exceeds the configured per-run cap."""


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token). Used for pre-call cost caps."""
    return max(1, math.ceil(len(text or "") / 4))


def estimate_cost_usd(model: AIModel | None, tokens_in: int, tokens_out: int) -> float:
    if model is None:
        return 0.0
    in_mtok = float(model.input_price_per_mtok or 0) / 1_000_000
    out_mtok = float(model.output_price_per_mtok or 0) / 1_000_000
    return round(tokens_in * in_mtok + tokens_out * out_mtok, 8)


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract the first complete JSON object from an LLM reply, tolerating
    markdown fences and prose around the object."""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        pass
    match = _JSON_RE.search(text or "")
    if not match:
        raise LLMError(f"no JSON object in LLM reply: {str(text)[:200]!r}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise LLMError(f"invalid JSON in LLM reply: {exc}") from exc


class LLMClient:
    """Thin, synchronous, OpenAI-compatible chat client with cost caps."""

    def __init__(
        self,
        provider: AIProvider,
        model: AIModel,
        api_key: str,
        *,
        timeout_seconds: int | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.api_key = api_key
        s = get_settings()
        self.timeout = timeout_seconds or s.ai_llm_timeout_seconds

    @property
    def model_id(self) -> str:
        return self.model.model_id

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        max_cost_usd: float = 0.05,
    ) -> dict[str, Any]:
        """Call the model; returns {content, tokens_in, tokens_out, cost_usd}.

        Raises :class:`CostLimitExceededError` before sending when the
        estimate exceeds ``max_cost_usd`` and :class:`LLMUnavailableError`
        on transport/auth errors.
        """
        payload_text = json.dumps(messages)
        est_in = estimate_tokens(payload_text) + estimate_tokens(self.model.display_name)
        est_out = max_tokens
        est_cost = estimate_cost_usd(self.model, est_in, est_out)
        if est_cost > max_cost_usd:
            raise CostLimitExceededError(
                f"estimated cost {est_cost:.6f} USD exceeds cap {max_cost_usd:.4f} USD"
            )

        url = f"{self.provider.base_url.rstrip('/')}/chat/completions"
        body: dict[str, Any] = {
            "model": self.model.model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailableError(f"provider HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, OSError) as exc:
            raise LLMUnavailableError(f"provider unreachable: {exc}") from exc
        except ValueError as exc:  # non-JSON response
            raise LLMUnavailableError(f"provider returned non-JSON: {exc}") from exc

        usage = data.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens") or est_in)
        tokens_out = int(usage.get("completion_tokens") or est_out)
        content = data["choices"][0]["message"]["content"]
        return {
            "content": content or "",
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": estimate_cost_usd(self.model, tokens_in, tokens_out),
        }


def get_llm_client(db: Session) -> LLMClient | None:
    """Return a configured client, or ``None`` to use deterministic engines."""
    provider, model, key = resolve_llm_config(db)
    if provider is None or model is None or not key:
        return None
    return LLMClient(provider, model, key)