"""Ticket API schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ContactIn(BaseModel):
    full_name: str | None = None
    title: str | None = None
    work_email: str | None = None
    phone: str | None = None
    profile_url: str | None = None


class CompanyIn(BaseModel):
    legal_name: str | None = None
    domain: str | None = None
    website: str | None = None


class TicketCreateIn(BaseModel):
    type_code: str = "GENERAL"
    type_name: str | None = None
    domain: str | None = None
    market_sector: str | None = None
    product: str | None = None
    service: str | None = None
    requirement: str | None = None
    requirement_details: dict[str, Any] | None = None
    intent_level: str | None = Field(default=None, pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    urgency: str | None = Field(default=None, pattern="^(NOW|WEEK|MONTH|UNKNOWN)$")
    budget: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=8)
    deal_size: str | None = None
    location: str | None = None
    jurisdiction: str | None = None
    timezone: str | None = None
    pain_point: str | None = None
    platform: str | None = None
    platform_url: str | None = None
    original_url: str | None = None
    official_website_url: str | None = None
    discovered_by: str | None = None
    source_id: str | None = None
    contact: ContactIn | None = None
    contact_role: str = "PRIMARY"
    company: CompanyIn | None = None
    owner_id: str | None = None
    notes: str | None = None

    @field_validator("intent_level", "urgency")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class TicketUpdateIn(BaseModel):
    domain: str | None = None
    market_sector: str | None = None
    product: str | None = None
    service: str | None = None
    requirement: str | None = None
    intent_level: str | None = None
    urgency: str | None = None
    budget: Decimal | None = None
    currency: str | None = None
    location: str | None = None
    jurisdiction: str | None = None
    timezone: str | None = None
    pain_point: str | None = None
    notes: str | None = None
    owner_id: str | None = None

    @field_validator("intent_level", "urgency")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        return v.upper() if v else v


class StatusTransitionIn(BaseModel):
    status: str = Field(min_length=3, max_length=32)
    reason: str | None = None


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    full_name: str
    title: str | None
    work_email: str | None
    phone: str | None
    profile_url: str | None
    company_id: str | None
    role: str | None = None  # set by serializer from TicketContact


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    legal_name: str
    trade_name: str | None
    domain: str | None
    website: str | None
    industry: str | None
    country: str | None
    is_verified: bool
    role: str | None = None


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reference: str
    status: str
    type_code: str
    type_name: str
    category_code: str | None
    domain: str | None
    market_sector: str | None
    product: str | None
    service: str | None
    requirement: str | None
    intent_level: str | None
    urgency: str | None
    budget: Decimal | None
    currency: str | None
    deal_size: str | None
    location: str | None
    jurisdiction: str | None
    timezone: str | None
    pain_point: str | None
    platform: str | None
    platform_url: str | None
    original_url: str | None
    official_website_url: str | None
    discovered_at: datetime | None
    published_at: datetime | None
    last_verified_at: datetime | None
    discovered_by: str | None
    lead_score: int | None
    intent_score: int | None
    risk_score: int | None
    confidence: float | None
    verification_status: str
    freshness: str
    duplicate_status: str
    owner_id: str | None
    notes: str | None
    last_activity_at: datetime | None
    created_at: datetime
    updated_at: datetime
    contacts: list[ContactOut] = []
    companies: list[CompanyOut] = []

    @staticmethod
    def _v(x):
        """Normalize enum-or-str values (session may hold raw strings)."""
        return x.value if hasattr(x, "value") and not isinstance(x, str) else x

    @classmethod
    def from_ticket(cls, t) -> "TicketOut":
        _v = cls._v
        contacts = [
            ContactOut(
                id=c.contact.id, full_name=c.contact.full_name, title=c.contact.title,
                work_email=c.contact.work_email, phone=c.contact.phone,
                profile_url=c.contact.profile_url, company_id=c.contact.company_id,
                role=c.role.value,
            )
            for c in t.ticket_contacts
        ]
        companies = [
            CompanyOut(
                id=k.company.id, legal_name=k.company.legal_name,
                trade_name=k.company.trade_name, domain=k.company.domain,
                website=k.company.website, industry=k.company.industry,
                country=k.company.country, is_verified=k.company.is_verified,
                role=k.role.value,
            )
            for k in t.ticket_companies
        ]
        budget = t.budget
        budget = Decimal(str(budget)) if budget is not None else None
        confidence = float(t.confidence) if t.confidence is not None else None
        return cls(
            id=t.id, reference=t.reference, status=t.status.code,
            type_code=t.type.code, type_name=t.type.name,
            category_code=t.category.code if t.category else None,
            domain=t.domain, market_sector=t.market_sector, product=t.product,
            service=t.service, requirement=t.requirement,
            intent_level=_v(t.intent_level) if t.intent_level else None,
            urgency=t.urgency, budget=budget, currency=t.currency, deal_size=t.deal_size,
            location=t.location, jurisdiction=t.jurisdiction, timezone=t.timezone,
            pain_point=t.pain_point, platform=t.platform, platform_url=t.platform_url,
            original_url=t.original_url, official_website_url=t.official_website_url,
            discovered_at=t.discovered_at, published_at=t.published_at,
            last_verified_at=t.last_verified_at, discovered_by=t.discovered_by,
            lead_score=t.lead_score, intent_score=t.intent_score, risk_score=t.risk_score,
            confidence=confidence,
            verification_status=_v(t.verification_status),
            freshness=_v(t.freshness), duplicate_status=_v(t.duplicate_status),
            owner_id=t.owner_id, notes=t.notes, last_activity_at=t.last_activity_at,
            created_at=t.created_at, updated_at=t.updated_at,
            contacts=contacts, companies=companies,
        )


class ScoreOut(BaseModel):
    lead: int
    intent: int
    risk: int
    confidence: float
    factors: dict[str, Any]


class VerificationRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    kind: str
    result: str
    verified_at: datetime | None
    verified_by: str | None
    confidence: float | None
    evidence: dict | None
    notes: str | None
