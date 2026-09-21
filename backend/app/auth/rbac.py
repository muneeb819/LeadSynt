"""RBAC architecture.

Permission codes follow ``resource:action``. Roles map to permission sets:

- admin    — everything, including user management and change control
- manager  — full read + oversight (QA, analytics, agents, settings read)
- operator — day-to-day ticket/lead work
- viewer   — read-only

``ensure_rbac_seeded`` is idempotent and runs at startup AND in the initial
migration data path, so roles/permissions exist in any environment.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ForbiddenError
from app.models.user import Permission, Role, RolePermission, User

# (code, resource, action, description)
PERMISSIONS: list[tuple[str, str, str, str]] = [
    ("tickets:read", "tickets", "read", "View tickets"),
    ("tickets:write", "tickets", "write", "Create/update tickets"),
    ("tickets:transition", "tickets", "transition", "Change ticket status"),
    ("tickets:delete", "tickets", "delete", "Archive/delete tickets"),
    ("leads:read", "leads", "read", "View qualified leads"),
    ("contacts:read", "contacts", "read", "View contacts"),
    ("contacts:write", "contacts", "write", "Create/update contacts"),
    ("companies:read", "companies", "read", "View companies"),
    ("companies:write", "companies", "write", "Create/update companies"),
    ("sources:read", "sources", "read", "View sources & connectors"),
    ("sources:run", "sources", "run", "Trigger connector runs"),
    ("verification:run", "verification", "run", "Run verifications"),
    ("scoring:run", "scoring", "run", "Run scoring"),
    ("outreach:read", "outreach", "read", "View outreach state"),
    ("outreach:send", "outreach", "send", "Send outreach (gated by suppression)"),
    ("outreach:manage", "outreach", "manage", "Manage outreach templates, follow-up rules and authorizations"),
    ("conversations:read", "conversations", "read", "View conversations"),
    ("deals:read", "deals", "read", "View deals"),
    ("deals:write", "deals", "write", "Create/update deals"),
    ("analytics:read", "analytics", "read", "View analytics"),
    ("agents:read", "agents", "read", "View AI agents & runs"),
    ("agents:run", "agents", "run", "Trigger AI agent runs"),
    ("qa:read", "qa", "read", "View QA findings"),
    ("qa:run", "qa", "run", "Trigger QA sweeps"),
    ("notifications:read", "notifications", "read", "View notifications"),
    ("settings:read", "settings", "read", "View system settings"),
    ("settings:write", "settings", "write", "Update system settings"),
    ("users:read", "users", "read", "View users"),
    ("users:manage", "users", "manage", "Manage users & roles"),
    ("audit:read", "audit", "read", "View audit logs"),
    ("admin:full", "admin", "full", "Full administrative control"),
]

ROLE_PERMISSIONS: dict[str, list[str] | "*"] = {
    "admin": "*",
    "manager": [
        "tickets:read", "leads:read", "contacts:read", "companies:read",
        "sources:read", "outreach:read", "conversations:read", "deals:read",
        "analytics:read", "agents:read", "agents:run", "qa:read", "qa:run",
        "notifications:read", "settings:read", "users:read", "audit:read",
        "verification:run", "scoring:run", "tickets:write",
        "tickets:transition", "contacts:write", "companies:write",
        "deals:write", "outreach:manage",
    ],
    "operator": [
        "tickets:read", "tickets:write", "tickets:transition", "leads:read",
        "contacts:read", "contacts:write", "companies:read", "companies:write",
        "sources:read", "outreach:read", "outreach:send", "conversations:read", "deals:read",
        "notifications:read", "verification:run", "scoring:run",
    ],
    "viewer": [
        "tickets:read", "leads:read", "contacts:read", "companies:read",
        "sources:read", "analytics:read", "notifications:read",
    ],
}

ROLE_DESCRIPTIONS = {
    "admin": "Full administrative control including change control",
    "manager": "Oversight, analytics, QA and coordination",
    "operator": "Day-to-day ticket, lead and outreach work",
    "viewer": "Read-only access",
}


def ensure_rbac_seeded(db: Session) -> None:
    """Idempotently create roles, permissions and mappings."""
    existing_perms = {p.code: p for p in db.execute(select(Permission)).scalars()}
    for code, resource, action, desc in PERMISSIONS:
        if code not in existing_perms:
            db.add(Permission(code=code, resource=resource, action=action, description=desc))
    db.flush()
    perms = {p.code: p for p in db.execute(select(Permission)).scalars()}

    for role_name, perms_list in ROLE_PERMISSIONS.items():
        role = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
        if role is None:
            role = Role(name=role_name, description=ROLE_DESCRIPTIONS.get(role_name), is_system=True)
            db.add(role)
            db.flush()
        have = {
            rp.permission.code
            for rp in db.execute(
                select(RolePermission)
                .join(Permission, RolePermission.permission_id == Permission.id)
                .where(RolePermission.role_id == role.id)
            ).scalars()
        }
        wanted: set[str] = set(perms.keys()) if perms_list == "*" else set(perms_list)
        for code in wanted - have:
            db.add(RolePermission(role_id=role.id, permission_id=perms[code].id))
    db.flush()


def get_role_permissions(db: Session, user: User) -> set[str]:
    codes: set[str] = set()
    for ur in user.user_roles:
        role = ur.role
        if role is None:
            continue
        for rp in db.execute(
            select(RolePermission)
            .join(Permission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        ).scalars():
            codes.add(rp.permission.code)
    return codes


def has_permission(db: Session, user: User, code: str) -> bool:
    return code in get_role_permissions(db, user)


def require_permission(code: str):
    """FastAPI dependency factory: 403 unless the user holds ``code``."""

    def checker(
        db: Session = Depends(None),  # replaced by composition in deps.py
        user: User = Depends(None),  # type: ignore[valid-type]
    ) -> User:
        if user is None or not has_permission(db, user, code):
            raise ForbiddenError(f"Missing permission: {code}")
        return user

    return checker
