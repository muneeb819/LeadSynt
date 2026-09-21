"""All LeadSynt SQLAlchemy models. Importing this package registers every
table on ``Base.metadata`` (used by Alembic autogenerate and tests)."""

from app.models.base import Base  # noqa: F401
from app.models.user import (  # noqa: F401
    Permission, Role, RolePermission, User, UserRole,
)
from app.models.ticket import (  # noqa: F401
    Ticket, TicketCategory, TicketStatus, TicketType,
)
from app.models.contact import (  # noqa: F401
    Contact, ContactEmail, ContactPhone, TicketContact,
)
from app.models.company import (  # noqa: F401
    Company, CompanyDomain, TicketCompany,
)
from app.models.source import (  # noqa: F401
    ConnectorRun, Source, SourceConnector, SourceRecord, TicketSource,
)
from app.models.verification import (  # noqa: F401
    EmailVerification, IdentityVerification, PhoneVerification,
    VerificationRecord,
)
from app.models.scoring import (  # noqa: F401
    IntentScoreSnapshot, LeadScoreSnapshot, RiskScoreSnapshot,
)
from app.models.ai import (  # noqa: F401
    AIAgent, AIDecision, AIEvidence, AIModel, AIProvider, AIRun,
)
from app.models.qa import QAFinding, QARun, QAReport  # noqa: F401
from app.models.ops import (  # noqa: F401
    AuditLog, ChangeRequest, ConsentRecord, Job, JobRun, Notification,
    SuppressionRecord, SystemSetting, WebhookEvent,
)
from app.models.conversation import Conversation, ConversationMessage  # noqa: F401
