"""Credential primitives: password hashing (bcrypt) and JWT issuance/verification.

The JWT secret is environment-driven only. Frontend never holds DB or signing
secrets; tokens are opaque bearer credentials validated by the backend.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from enum import StrEnum

import bcrypt
import jwt

from app.core.config import get_settings


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(password: str) -> str:
    s = get_settings()
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=s.bcrypt_rounds)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        return False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ttl(kind: TokenType) -> timedelta:
    s = get_settings()
    if kind is TokenType.ACCESS:
        return timedelta(minutes=s.jwt_access_token_ttl_minutes)
    return timedelta(days=s.jwt_refresh_token_ttl_days)


def create_token(user_id: str, kind: TokenType, role: str | None = None) -> str:
    s = get_settings()
    now = _now()
    payload = {
        "iss": s.jwt_issuer,
        "sub": user_id,
        "type": kind.value,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + _ttl(kind)).timestamp()),
    }
    if role:
        payload["role"] = role
    return jwt.encode(payload, s.secret_key, algorithm=s.jwt_algorithm)


def decode_token(token: str, expected_type: TokenType = TokenType.ACCESS) -> dict:
    """Decode + validate a JWT. Raises ``TokenError`` on any problem."""
    s = get_settings()
    try:
        payload = jwt.decode(
            token,
            s.secret_key,
            algorithms=[s.jwt_algorithm],
            issuer=s.jwt_issuer,
            options={"require": ["exp", "sub", "type", "jti"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenError(f"Invalid token: {exc.__class__.__name__}") from exc
    if payload.get("type") != expected_type.value:
        raise TokenError("Wrong token type")
    return payload


class TokenError(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""
