"""Deterministic text helpers used by the Phase A agents.

Conservative by design: patterns must be explicit to be accepted; anything
ambiguous stays UNKNOWN (never guessed).
"""

from __future__ import annotations

import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\+?[0-9][0-9\-()\s]{6,19}")
BUDGET_KW_RE = re.compile(
    r"(?i)\b(?:budget|amount|worth|value|spend|award|contract value)\b[^0-9]{0,40}"
    r"\$?\s*([\d][\d,\.]*)\s*([kmbt]|(?:million|thousand|billion))?\b"
)
BUDGET_SYMBOL_RE = re.compile(r"\$\s*([\d][\d,\.]*)\s*([kmbt]|(?:million|thousand|billion))?\b")
QUARTER_RE = re.compile(r"(?i)\bq[1-4]\s*\d{4}\b")
ISO_DATE_RE = re.compile(r"\b(19|20)\d{2}[-/](?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12]\d|3[01])\b")
MONTH_DATE_RE = re.compile(
    r"(?i)\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|"
    r"aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
    r"\.?\s+\d{1,2},?\s+\d{4}\b"
)
SUFFIX_RE = re.compile(r"(?i)\b(inc|llc|ltd|limited|corp|corporation|gmbh|sarl|s\\.?a\\.?|bv|pty)\b\.?$")
PUNCT_RE = re.compile(r"[^\w\s]")
WS_RE = re.compile(r"\s+")

_SCALE = {
    "k": 1_000, "thousand": 1_000,
    "m": 1_000_000, "million": 1_000_000,
    "b": 1_000_000_000, "billion": 1_000_000_000,
    "t": 1_000_000_000_000,
}


def extract_emails(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in EMAIL_RE.finditer(text or "")})


def extract_phones(text: str) -> list[str]:
    out: list[str] = []
    for m in PHONE_RE.finditer(text or ""):
        digits = re.sub(r"\D", "", m.group(0))
        if 8 <= len(digits) <= 15 and digits not in out:
            out.append(digits)
    return out


def _number_with_scale(value: str, scale: str | None) -> float | None:
    try:
        num = float(value.replace(",", ""))
    except ValueError:
        return None
    return num * _SCALE.get((scale or "").lower(), 1.0)


def extract_budget(text: str) -> list[float]:
    """Numeric budget hints from text ($12M, 'budget: 50000', 1.2 million...)."""
    from itertools import chain

    hits: list[float] = []
    for m in chain(BUDGET_KW_RE.finditer(text or ""), BUDGET_SYMBOL_RE.finditer(text or "")):
        val = _number_with_scale(m.group(1), m.group(2) if m.lastindex and m.lastindex >= 2 else None)
        if val is not None and val > 0:
            hits.append(val)
    return hits


def extract_dates(text: str) -> list[str]:
    out: list[str] = []
    for regex in (QUARTER_RE, ISO_DATE_RE, MONTH_DATE_RE):
        for m in regex.finditer(text or ""):
            token = m.group(0)
            if token not in out:
                out.append(token)
    return out


def base_domain(domain: str | None) -> str | None:
    """Reduce a host/email domain to its registrable base (last two labels)."""
    if not domain:
        return None
    host = domain.strip().lower().rstrip(".")
    if "@" in host:
        host = host.rsplit("@", 1)[1]
    labels = [lab for lab in host.split(".") if lab]
    if len(labels) <= 2:
        return ".".join(labels) if labels else None
    return ".".join(labels[-2:])


def normalize_company_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = SUFFIX_RE.sub("", name.strip())
    cleaned = PUNCT_RE.sub(" ", cleaned)
    cleaned = WS_RE.sub(" ", cleaned).strip().lower()
    return cleaned or None


def name_tokens(name: str | None) -> set[str]:
    norm = normalize_company_name(name)
    return set((norm or "").split())


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)