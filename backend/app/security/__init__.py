"""Security helpers (webhook signatures, hmac utilities)."""

from __future__ import annotations

import hashlib
import hmac
import time


def sign_payload(secret: str, body: bytes, timestamp: int | None = None) -> tuple[str, int]:
    """HMAC-SHA256 signature of ``timestamp.body`` (webhook convention)."""
    ts = int(timestamp or time.time())
    msg = f"{ts}.".encode() + body
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return sig, ts


def verify_signature(
    secret: str,
    body: bytes,
    signature: str | None,
    timestamp: str | None,
    tolerance_seconds: int = 300,
) -> bool:
    """Constant-time verification of a signed webhook payload."""
    if not signature or timestamp is None:
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > tolerance_seconds:
        return False
    expected, _ = sign_payload(secret, body, ts)
    return hmac.compare_digest(expected, signature)
