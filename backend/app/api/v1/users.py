"""User management (RBAC-gated)."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.auth.rbac import ensure_rbac_seeded, get_role_permissions
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.models.user import Role, User, UserRole
from app.schemas.common import Envelope
from app.services.audit_service import audit

router = APIRouter()


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    roles: list[str]
    is_active: bool
    last_login_at: str | None


class UserCreateIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    password: str = Field(min_length=10, max_length=128)
    role: str = "viewer"


def _out(u: User) -> UserOut:
    return UserOut(
        id=u.id, email=u.email, full_name=u.full_name, roles=u.role_names,
        is_active=u.is_active,
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )


@router.get("", response_model=Envelope)
def list_users(
    user=Depends(require_permission("users:read")), db: Session = Depends(get_db)
):
    users = db.execute(select(User).order_by(User.created_at)).scalars().all()
    return Envelope(data=[_out(u).model_dump() for u in users])


@router.post("", status_code=201, response_model=Envelope)
def create_user(
    payload: UserCreateIn,
    user=Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
):
    ensure_rbac_seeded(db)
    if db.execute(select(User).where(User.email == payload.email.lower())).scalar_one_or_none():
        raise ConflictError("A user with this email already exists")
    new_user = User(
        email=payload.email.lower(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
    )
    db.add(new_user)
    db.flush()
    role = db.execute(select(Role).where(Role.name == payload.role)).scalar_one_or_none()
    if role is None:
        raise NotFoundError(f"Unknown role: {payload.role}")
    db.add(UserRole(user_id=new_user.id, role_id=role.id))
    audit(db, action="user.created", actor_id=user.id, actor_type="user",
          resource_type="user", resource_id=new_user.id,
          after={"email": new_user.email, "role": payload.role})
    db.commit()
    return Envelope(data=_out(new_user).model_dump())


@router.post("/{user_id}/deactivate", response_model=Envelope)
def deactivate(
    user_id: str,
    user=Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
):
    target = db.get(User, user_id)
    if target is None:
        raise NotFoundError("User not found")
    target.is_active = False
    audit(db, action="user.deactivated", actor_id=user.id, actor_type="user",
          resource_type="user", resource_id=target.id)
    db.commit()
    return Envelope(data={"id": target.id, "is_active": False})
