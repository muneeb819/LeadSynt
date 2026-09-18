"""Shared FastAPI dependencies: authn, authz, db."""

from __future__ import annotations

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.rbac import has_permission
from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import TokenError, TokenType, decode_token
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing bearer token")
    try:
        payload = decode_token(credentials.credentials, TokenType.ACCESS)
    except TokenError as exc:
        raise UnauthorizedError(str(exc))
    user = db.get(User, payload["sub"])
    if user is None:
        raise UnauthorizedError("User no longer exists")
    if not user.is_active:
        raise ForbiddenError("User account is deactivated")
    request.state.user_id = user.id
    return user


def require_permission(code: str):
    """Composed dependency: authenticated + permission-checked."""

    def checker(
        request: Request,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not has_permission(db, user, code):
            raise ForbiddenError(f"Missing permission: {code}")
        return user

    return checker
