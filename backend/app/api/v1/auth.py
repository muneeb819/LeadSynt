"""Authentication endpoints: register (dev-gated), login, refresh, me."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.auth.rbac import ensure_rbac_seeded, get_role_permissions, ROLE_PERMISSIONS
from app.core.config import get_settings
from app.core.database import get_db
from app.core.exceptions import BadRequestError, ConflictError, UnauthorizedError
from app.core.security import TokenError, TokenType, create_token, decode_token, hash_password, verify_password
from app.models.user import Role, User, UserRole
from app.schemas.auth import LoginIn, MeOut, RefreshIn, RegisterIn, TokenOut
from app.services.audit_service import audit
from app.queues.events import EventBus

router = APIRouter()


def _assign_role(db: Session, user: User, role_name: str) -> None:
    role = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
    if role is None:
        raise BadRequestError(f"Unknown role: {role_name}")
    db.add(UserRole(user_id=user.id, role_id=role.id))
    db.flush()


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.post("/register", status_code=201)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    s = get_settings()
    if not s.allow_self_registration:
        raise BadRequestError("Self-registration is disabled in this environment")
    ensure_rbac_seeded(db)
    if db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none():
        raise ConflictError("A user with this email already exists")
    user = User(
        email=payload.email.lower(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()
    role_name = s.default_registration_role if s.default_registration_role in ROLE_PERMISSIONS else "viewer"
    _assign_role(db, user, role_name)
    audit(db, action="auth.register", actor_id=user.id, actor_type="user",
          resource_type="user", resource_id=user.id, meta={"role": role_name},
          ip_address=request.client.host if request.client else None,
          request_id=_request_id(request))
    db.commit()
    return {"id": user.id, "email": user.email, "role": role_name}


@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        audit(db, action="auth.login.failed", actor_type="user",
              meta={"email": payload.email.lower()},
              ip_address=request.client.host if request.client else None,
              request_id=_request_id(request))
        db.commit()
        raise UnauthorizedError("Invalid email or password")
    if not user.is_active:
        raise UnauthorizedError("Account is deactivated")
    user.last_login_at = datetime.now(timezone.utc)
    role = user.primary_role or "viewer"
    access = create_token(user.id, TokenType.ACCESS, role=role)
    refresh = create_token(user.id, TokenType.REFRESH)
    audit(db, action="auth.login", actor_id=user.id, actor_type="user",
          resource_type="user", resource_id=user.id,
          ip_address=request.client.host if request.client else None,
          request_id=_request_id(request))
    db.commit()
    return TokenOut(access_token=access, refresh_token=refresh)


@router.post("/refresh")
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    try:
        token_payload = decode_token(payload.refresh_token, TokenType.REFRESH)
    except TokenError as exc:
        raise UnauthorizedError(str(exc))
    user = db.get(User, token_payload["sub"])
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or deactivated")
    role = user.primary_role or "viewer"
    return TokenOut(
        access_token=create_token(user.id, TokenType.ACCESS, role=role),
        refresh_token=create_token(user.id, TokenType.REFRESH),
    )


@router.get("/me", response_model=MeOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return MeOut(
        id=user.id, email=user.email, full_name=user.full_name,
        roles=user.role_names, is_active=user.is_active, timezone=user.timezone,
    )
