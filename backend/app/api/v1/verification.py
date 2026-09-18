"""Verification API: run email/phone/company checks, view history."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.core.exceptions import BadRequestError, NotFoundError
from app.schemas.common import Envelope
from app.schemas.ticket import VerificationRecordOut
from app.services.verification_service import (
    ticket_verification_history, verify_company, verify_email_address,
    verify_phone_number,
)

router = APIRouter()


class EmailVerifyIn(BaseModel):
    """``email`` is a plain string on purpose: the verification service
    performs the deterministic syntax check and records the outcome —
    schema-level rejection would skip the verification history."""

    ticket_id: str
    email: str = Field(min_length=3, max_length=320)


class PhoneVerifyIn(BaseModel):
    ticket_id: str
    phone: str


class CompanyVerifyIn(BaseModel):
    ticket_id: str
    company_id: str


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


@router.post("/email", response_model=Envelope)
def verify_email(
    payload: EmailVerifyIn,
    request: Request,
    user=Depends(require_permission("verification:run")),
    db: Session = Depends(get_db),
):
    from app.models.ticket import Ticket

    if db.get(Ticket, payload.ticket_id) is None:
        raise NotFoundError("Ticket not found")
    rec = verify_email_address(db, email=payload.email, ticket_id=payload.ticket_id,
                               verified_by=f"user:{user.id}")
    db.commit()
    return Envelope(data=VerificationRecordOut.model_validate(rec).model_dump(),
                    request_id=_request_id(request))


@router.post("/phone", response_model=Envelope)
def verify_phone(
    payload: PhoneVerifyIn,
    request: Request,
    user=Depends(require_permission("verification:run")),
    db: Session = Depends(get_db),
):
    from app.models.ticket import Ticket

    if db.get(Ticket, payload.ticket_id) is None:
        raise NotFoundError("Ticket not found")
    rec = verify_phone_number(db, phone=payload.phone, ticket_id=payload.ticket_id,
                              verified_by=f"user:{user.id}")
    db.commit()
    return Envelope(data=VerificationRecordOut.model_validate(rec).model_dump(),
                    request_id=_request_id(request))


@router.post("/company", response_model=Envelope)
def verify_company_endpoint(
    payload: CompanyVerifyIn,
    request: Request,
    user=Depends(require_permission("verification:run")),
    db: Session = Depends(get_db),
):
    from app.models.ticket import Ticket

    if db.get(Ticket, payload.ticket_id) is None:
        raise NotFoundError("Ticket not found")
    rec = verify_company(db, company_id=payload.company_id, ticket_id=payload.ticket_id,
                         verified_by=f"user:{user.id}")
    db.commit()
    return Envelope(data=VerificationRecordOut.model_validate(rec).model_dump(),
                    request_id=_request_id(request))


@router.get("/history/{ticket_id}", response_model=Envelope)
def history(
    ticket_id: str,
    user=Depends(require_permission("tickets:read")),
    db: Session = Depends(get_db),
):
    from app.models.ticket import Ticket

    if db.get(Ticket, ticket_id) is None:
        raise NotFoundError("Ticket not found")
    recs = ticket_verification_history(db, ticket_id)
    return Envelope(data=[VerificationRecordOut.model_validate(r).model_dump() for r in recs])
