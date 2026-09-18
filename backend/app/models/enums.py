"""Domain enumerations (single source of truth, shared by models/schemas).

Enum columns are stored as VARCHAR + CHECK constraint (``native_enum=False``)
which is the portable, SQL Server safe choice.
"""

from __future__ import annotations

from enum import StrEnum


class TicketStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    INGESTED = "INGESTED"
    PROCESSING = "PROCESSING"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    VERIFICATION_PENDING = "VERIFICATION_PENDING"
    VERIFIED = "VERIFIED"
    QUALIFIED = "QUALIFIED"
    OUTREACH_READY = "OUTREACH_READY"
    OUTREACH_ACTIVE = "OUTREACH_ACTIVE"
    REPLIED = "REPLIED"
    HOT_LEAD = "HOT_LEAD"
    AWAITING_HUMAN = "AWAITING_HUMAN"
    MEETING_BOOKED = "MEETING_BOOKED"
    NEGOTIATION = "NEGOTIATION"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    WON = "WON"
    LOST = "LOST"
    DISQUALIFIED = "DISQUALIFIED"
    DUPLICATE = "DUPLICATE"
    EXPIRED = "EXPIRED"
    ARCHIVED = "ARCHIVED"


class VerificationStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class DuplicateStatus(StrEnum):
    UNIQUE = "UNIQUE"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    DUPLICATE = "DUPLICATE"
    MERGED = "MERGED"


class IntentLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Freshness(StrEnum):
    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"


class VerificationKind(StrEnum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    COMPANY = "COMPANY"
    DIGITAL_IDENTITY = "DIGITAL_IDENTITY"


class VerificationResult(StrEnum):
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    UNVERIFIABLE = "UNVERIFIABLE"
    UNKNOWN = "UNKNOWN"


class ScoreKind(StrEnum):
    LEAD = "LEAD"
    INTENT = "INTENT"
    RISK = "RISK"


class AgentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DISABLED = "DISABLED"


class RunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class FindingSeverity(StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class FindingStatus(StrEnum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"


class QATrigger(StrEnum):
    MANUAL = "MANUAL"
    SCHEDULED = "SCHEDULED"
    WEBHOOK = "WEBHOOK"


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SourceKind(StrEnum):
    API = "API"
    PUBLIC_WEB = "PUBLIC_WEB"
    FEED = "FEED"
    LICENSED_DATASET = "LICENSED_DATASET"
    SEARCH = "SEARCH"
    MARKETPLACE = "MARKETPLACE"
    USER_INTEGRATION = "USER_INTEGRATION"
    MANUAL = "MANUAL"


class AuthMethod(StrEnum):
    NONE = "NONE"
    API_KEY = "API_KEY"
    OAUTH2 = "OAUTH2"
    BASIC = "BASIC"
    BEARER = "BEARER"
    WEBHOOK_SIGNATURE = "WEBHOOK_SIGNATURE"


class ConnectorHealth(StrEnum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    UNKNOWN = "UNKNOWN"


class TicketContactRole(StrEnum):
    PRIMARY = "PRIMARY"
    DECISION_MAKER = "DECISION_MAKER"
    INFLUENCER = "INFLUENCER"
    CC = "CC"


class TicketCompanyRole(StrEnum):
    PRIMARY = "PRIMARY"
    RELATED = "RELATED"


class NotificationChannel(StrEnum):
    IN_APP = "IN_APP"
    EMAIL = "EMAIL"
    SMS = "SMS"
    WEBHOOK = "WEBHOOK"


class NotificationType(StrEnum):
    TICKET_UPDATE = "TICKET_UPDATE"
    HANDOVER = "HANDOVER"
    VERIFICATION = "VERIFICATION"
    QA_ALERT = "QA_ALERT"
    CONNECTOR_ALERT = "CONNECTOR_ALERT"
    SYSTEM = "SYSTEM"


class ChangeRequestStatus(StrEnum):
    PROPOSED = "PROPOSED"
    PLAN_READY = "PLAN_READY"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPLIED = "APPLIED"
    ROLLED_BACK = "ROLLED_BACK"


class ConsentStatus(StrEnum):
    GRANTED = "GRANTED"
    WITHDRAWN = "WITHDRAWN"
