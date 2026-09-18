"""Settings API — dynamic, admin-tunable configuration (spec §24)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.configuration import ensure_defaults, list_settings, set_setting
from app.schemas.common import Envelope
from app.services.audit_service import audit


class SettingUpdateIn(BaseModel):
    value: dict


router = APIRouter()


@router.get("", response_model=Envelope)
def get_settings_endpoint(
    user=Depends(require_permission("settings:read")), db: Session = Depends(get_db)
):
    ensure_defaults(db)
    db.commit()
    rows = list_settings(db)
    return Envelope(data=[
        {"key": r.key, "value": r.value, "description": r.description,
         "updated_by": r.updated_by,
         "updated_at": r.updated_at.isoformat() if r.updated_at else None}
        for r in rows
    ])


@router.put("/{key}", response_model=Envelope)
def update_setting(
    key: str,
    payload: SettingUpdateIn,
    request: Request,
    user=Depends(require_permission("settings:write")),
    db: Session = Depends(get_db),
):
    ensure_defaults(db)
    row = set_setting(db, key, payload.value, updated_by=user.id)
    audit(db, action="setting.updated", actor_id=user.id, actor_type="user",
          resource_type="system_setting", resource_id=row.id,
          after={"key": key, "value": payload.value},
          request_id=getattr(request.state, "request_id", None))
    db.commit()
    return Envelope(data={"key": row.key, "value": row.value})
