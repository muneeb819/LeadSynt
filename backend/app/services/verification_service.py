"""Verification service — history-storing, deterministic checks.

Foundation providers:
- email: syntax + structure check, disposable-domain blocklist. MX lookup and
  provider verification are later-phase plugs behind the same record shape.
- phone: E.164-style format check + country inference for a small set of
  known calling codes (others stay UNKNOWN — never guessed).

Results are stored as immutable history (verification_records + detail
tables). Unknowns are stored as UNKNOWN, never fabricated.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    VerificationKind, VerificationResult, VerificationStatus,
)
from app.models.ticket import Ticket
from app.models.verification import (
    EmailVerification, PhoneVerification, VerificationRecord,
)

DISPOSABLE_DOMAINS = {
    "mailinator.com", "yopmail.com", "tempmail.com", "temp-mail.org",
    "10minutemail.com", "guerrillamail.com", "trashmail.com", "fakeinbox.com",
    "throwawaymail.com", "getnada.com", "sharklasers.com", "maildrop.cc",
    "dispostable.com", "tempinbox.com",
}

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9\-()\s]{8,20}$")

_COUNTRY_CODES = {
    "92": "PK", "1": "US", "44": "GB", "49": "DE", "33": "FR", "61": "AU",
    "65": "SG", "971": "AE", "86": "CN", "91": "IN", "81": "JP", "82": "KR",
    "20": "EG", "234": "NG", "27": "ZA", "55": "BR", "48": "PL", "90": "TR",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def verify_email_address(
    db: Session,
    *,
    email: str,
    ticket_id: str | None = None,
    verified_by: str = "verification-service",
) -> VerificationRecord:
    email = (email or "").strip().lower()
    syntax_ok = bool(EMAIL_RE.match(email)) and len(email) <= 320 and email.count("@") == 1
    domain = email.split("@", 1)[1] if "@" in email else None
    is_disposable = domain in DISPOSABLE_DOMAINS if domain else False

    if not syntax_ok:
        result, confidence, notes = VerificationResult.FAILED, 0.95, "email syntax invalid"
    elif is_disposable:
        result, confidence, notes = VerificationResult.FAILED, 0.9, f"disposable domain: {domain}"
    else:
        # MX/provider checks are provider-gated; without a provider they are
        # UNKNOWN, not guesses.
        result, confidence, notes = VerificationResult.VERIFIED, 0.6, (
            "syntax valid, non-disposable domain; MX/provider check pending "
            "(provider not configured)"
        )

    rec = VerificationRecord(
        entity_kind=VerificationKind.EMAIL,
        entity_ref=ticket_id or email,
        kind=VerificationKind.EMAIL,
        result=result,
        verified_at=_utcnow(),
        verified_by=verified_by,
        confidence=confidence,
        evidence={"email": email, "domain": domain, "disposable": is_disposable},
        notes=notes,
    )
    db.add(rec)
    db.flush()
    db.add(
        EmailVerification(
            record_id=rec.id,
            email=email,
            syntax_ok=syntax_ok,
            domain=domain,
            mx_present=None,
            is_disposable=is_disposable,
            is_catch_all=None,
            provider="none",
            details={"notes": notes},
        )
    )
    if ticket_id:
        _rollup_ticket_status(db, ticket_id)
    db.flush()
    return rec


def verify_phone_number(
    db: Session,
    *,
    phone: str,
    ticket_id: str | None = None,
    verified_by: str = "verification-service",
) -> VerificationRecord:
    phone = (phone or "").strip()
    digits = re.sub(r"\D", "", phone)
    valid_format = bool(PHONE_RE.match(phone)) and 8 <= len(digits) <= 15
    country = next((cc for code, cc in _COUNTRY_CODES.items() if digits.startswith(code) and len(code) >= 2), None)

    if not valid_format:
        result, confidence, notes = VerificationResult.FAILED, 0.9, "phone format invalid"
    else:
        result, confidence, notes = VerificationResult.VERIFIED, 0.7, (
            "format valid; carrier/line-type checks pending (provider not configured)"
        )

    rec = VerificationRecord(
        entity_kind=VerificationKind.PHONE,
        entity_ref=ticket_id or phone,
        kind=VerificationKind.PHONE,
        result=result,
        verified_at=_utcnow(),
        verified_by=verified_by,
        confidence=confidence,
        evidence={"phone": phone, "country": country},
        notes=notes,
    )
    db.add(rec)
    db.flush()
    db.add(
        PhoneVerification(
            record_id=rec.id,
            phone=phone,
            is_valid_format=valid_format,
            country=country,
            carrier=None,
            line_type=None,
            provider="none",
            details={"notes": notes},
        )
    )
    if ticket_id:
        _rollup_ticket_status(db, ticket_id)
    db.flush()
    return rec


def verify_company(
    db: Session,
    *,
    company_id: str,
    ticket_id: str | None = None,
    verified_by: str = "verification-service",
) -> VerificationRecord:
    """Foundation: domain/website presence check only; cross-reference checks
    come with the Enrichment/Verification agents."""
    from app.models.company import Company

    company = db.get(Company, company_id)
    has_domain = bool(company and company.domain)
    has_website = bool(company and company.website)
    if has_domain and has_website:
        result, confidence, notes = VerificationResult.VERIFIED, 0.5, "domain + official website present; cross-reference pending"
    elif has_domain or has_website:
        result, confidence, notes = VerificationResult.VERIFIED, 0.4, "partial company identity; cross-reference pending"
    else:
        result, confidence, notes = VerificationResult.UNVERIFIABLE, 0.3, "no domain/website to verify"

    rec = VerificationRecord(
        entity_kind=VerificationKind.COMPANY,
        entity_ref=company_id,
        kind=VerificationKind.COMPANY,
        result=result,
        verified_at=_utcnow(),
        verified_by=verified_by,
        confidence=confidence,
        evidence={"company_id": company_id, "domain": company.domain if company else None,
                  "website": company.website if company else None},
        notes=notes,
    )
    db.add(rec)
    db.flush()
    if ticket_id:
        _rollup_ticket_status(db, ticket_id)
    db.flush()
    return rec


def _rollup_ticket_status(db: Session, ticket_id: str) -> None:
    """Ticket verification status = rollup of its latest verification history.

    VERIFIED  — at least one VERIFIED and no FAILED after it
    FAILED    — latest result FAILED
    PENDING   — latest result UNVERIFIABLE
    UNVERIFIED — no history
    Unknowns stay UNKNOWN (never guessed).
    """
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        return
    latest = db.execute(
        select(VerificationRecord)
        .where(VerificationRecord.entity_ref == ticket_id)
        .order_by(VerificationRecord.created_at.desc())
        .limit(1)
    ).scalars().first()
    has_any = db.execute(
        select(VerificationRecord.id).where(VerificationRecord.entity_ref == ticket_id).limit(1)
    ).first()
    if has_any is None:
        ticket.verification_status = VerificationStatus.UNVERIFIED
        return
    ticket.last_verified_at = latest.verified_at if latest else None
    if latest is None:
        return
    if latest.result is VerificationResult.VERIFIED:
        ticket.verification_status = VerificationStatus.VERIFIED
    elif latest.result is VerificationResult.FAILED:
        ticket.verification_status = VerificationStatus.FAILED
    elif latest.result is VerificationResult.UNVERIFIABLE:
        ticket.verification_status = VerificationStatus.PENDING
    else:
        ticket.verification_status = VerificationStatus.UNKNOWN


def ticket_verification_history(db: Session, ticket_id: str) -> list[VerificationRecord]:
    return list(
        db.execute(
            select(VerificationRecord)
            .where(VerificationRecord.entity_ref == ticket_id)
            .order_by(VerificationRecord.created_at.desc())
        ).scalars().all()
    )
