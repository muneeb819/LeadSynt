"""Sources API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.enums import SourceKind
from app.models.source import Source
from app.schemas.common import Envelope
from app.services.audit_service import audit

router = APIRouter()


class SourceOut(BaseModel):
    id: str
    name: str
    platform: str | None
    kind: str
    base_url: str | None
    description: str | None
    is_active: bool
    compliance_notes: str | None


def _out(s: Source) -> dict:
    return SourceOut(
        id=s.id, name=s.name, platform=s.platform, kind=s.kind.value,
        base_url=s.base_url, description=s.description, is_active=s.is_active,
        compliance_notes=s.compliance_notes,
    ).model_dump()


class SourceCreateIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    platform: str | None = None
    kind: str = "MANUAL"
    base_url: str | None = None
    description: str | None = None
    compliance_notes: str | None = Field(default=None, max_length=2000)


@router.get("", response_model=Envelope)
def sources(
    user=Depends(require_permission("sources:read")), db: Session = Depends(get_db)
):
    rows = db.execute(select(Source).order_by(Source.name)).scalars().all()
    return Envelope(data=[_out(s) for s in rows])


@router.post("", status_code=201, response_model=Envelope)
def create_source(
    payload: SourceCreateIn,
    user=Depends(require_permission("users:manage")),
    db: Session = Depends(get_db),
):
    try:
        kind = SourceKind(payload.kind.upper())
    except ValueError:
        raise BadRequestError(f"Unknown source kind: {payload.kind}")
    if db.execute(select(Source).where(Source.name == payload.name)).scalar_one_or_none():
        raise BadRequestError("Source name already exists")
    src = Source(
        name=payload.name, platform=payload.platform, kind=kind,
        base_url=payload.base_url, description=payload.description,
        compliance_notes=payload.compliance_notes or "Authorized channel; no bypasses.",
    )
    db.add(src)
    db.flush()
    audit(db, action="source.created", actor_id=user.id, actor_type="user",
          resource_type="source", resource_id=src.id, after={"name": src.name, "kind": kind.value})
    db.commit()
    return Envelope(data=_out(src))
