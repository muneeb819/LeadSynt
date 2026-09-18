"""Contacts API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import NotFoundError
from app.core.pagination import PageResult
from app.models.contact import Contact
from app.schemas.common import Envelope
from app.services.audit_service import audit

router = APIRouter()


class ContactOut(BaseModel):
    id: str
    full_name: str
    title: str | None
    work_email: str | None
    phone: str | None
    profile_url: str | None
    company_id: str | None
    locale: str | None


def _out(c: Contact) -> dict:
    return ContactOut(
        id=c.id, full_name=c.full_name, title=c.title, work_email=c.work_email,
        phone=c.phone, profile_url=c.profile_url, company_id=c.company_id,
        locale=c.locale,
    ).model_dump()


@router.get("", response_model=Envelope)
def contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = Query(None, max_length=120),
    user=Depends(require_permission("contacts:read")),
    db: Session = Depends(get_db),
):
    filters = []
    if q:
        filters.append(
            (Contact.full_name.ilike(f"%{q}%")) | (Contact.work_email.ilike(f"%{q}%"))
        )
    total = db.execute(
        select(func.count()).select_from(Contact).where(*filters) if filters
        else select(func.count()).select_from(Contact)
    ).scalar_one()
    rows = db.execute(
        select(Contact).where(*filters).order_by(Contact.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    result = PageResult(items=[_out(c) for c in rows], page=page,
                        page_size=page_size, total=total,
                        total_pages=(total + page_size - 1) // page_size)
    return Envelope(data=result.to_envelope())


@router.get("/{contact_id}", response_model=Envelope)
def contact_detail(
    contact_id: str,
    user=Depends(require_permission("contacts:read")),
    db: Session = Depends(get_db),
):
    c = db.get(Contact, contact_id)
    if c is None:
        raise NotFoundError("Contact not found")
    return Envelope(data=_out(c))


@router.post("/{contact_id}/suppress", status_code=201, response_model=Envelope)
def suppress(
    contact_id: str,
    request: Request,
    reason: str = Query("opt_out", max_length=200),
    user=Depends(require_permission("contacts:write")),
    db: Session = Depends(get_db),
):
    """Add a contact to DO-NOT-CONTACT (privacy guardrail)."""
    from app.services.suppression_service import add_suppression

    c = db.get(Contact, contact_id)
    if c is None:
        raise NotFoundError("Contact not found")
    rec = add_suppression(db, scope="contact", value=c.id, contact_id=c.id,
                          reason=reason, source="user")
    if c.work_email:
        add_suppression(db, scope="email", value=c.work_email, contact_id=c.id,
                        reason=reason, source="user")
    audit(db, action="contact.suppressed", actor_id=user.id, actor_type="user",
          resource_type="contact", resource_id=c.id, meta={"reason": reason})
    db.commit()
    return Envelope(data={"suppression_id": rec.id})
