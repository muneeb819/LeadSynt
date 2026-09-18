"""Companies API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import NotFoundError
from app.core.pagination import PageResult
from app.models.company import Company
from app.schemas.common import Envelope

router = APIRouter()


class CompanyOut(BaseModel):
    id: str
    legal_name: str
    trade_name: str | None
    domain: str | None
    website: str | None
    industry: str | None
    size_band: str | None
    country: str | None
    is_verified: bool


def _out(c: Company) -> dict:
    return CompanyOut(
        id=c.id, legal_name=c.legal_name, trade_name=c.trade_name, domain=c.domain,
        website=c.website, industry=c.industry, size_band=c.size_band,
        country=c.country, is_verified=c.is_verified,
    ).model_dump()


@router.get("", response_model=Envelope)
def companies(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    q: str | None = Query(None, max_length=120),
    user=Depends(require_permission("companies:read")),
    db: Session = Depends(get_db),
):
    filters = []
    if q:
        like = f"%{q}%"
        filters.append(or_(Company.legal_name.ilike(like), Company.domain.ilike(like)))
    total = db.execute(
        select(func.count()).select_from(Company).where(*filters)
    ).scalar_one()
    rows = db.execute(
        select(Company).where(*filters).order_by(Company.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    result = PageResult(items=[_out(c) for c in rows], page=page,
                        page_size=page_size, total=total,
                        total_pages=(total + page_size - 1) // page_size)
    return Envelope(data=result.to_envelope())


@router.get("/{company_id}", response_model=Envelope)
def company_detail(
    company_id: str,
    user=Depends(require_permission("companies:read")),
    db: Session = Depends(get_db),
):
    c = db.get(Company, company_id)
    if c is None:
        raise NotFoundError("Company not found")
    return Envelope(data=_out(c))
