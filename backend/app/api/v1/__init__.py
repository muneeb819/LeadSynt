"""API v1 router aggregation. Versioned under /api/v1."""

from fastapi import APIRouter

from app.api.v1 import (
    admin, agents, analytics, auth, companies, connectors, contacts,
    handover, health, leads, notifications, outreach, qa, scoring, settings,
    sources, tickets, users, verification,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(tickets.router, prefix="/tickets", tags=["tickets"])
api_router.include_router(leads.router, prefix="/leads", tags=["leads"])
api_router.include_router(contacts.router, prefix="/contacts", tags=["contacts"])
api_router.include_router(companies.router, prefix="/companies", tags=["companies"])
api_router.include_router(sources.router, prefix="/sources", tags=["sources"])
api_router.include_router(connectors.router, prefix="/connectors", tags=["connectors"])
api_router.include_router(verification.router, prefix="/verification", tags=["verification"])
api_router.include_router(scoring.router, prefix="/scoring", tags=["scoring"])
api_router.include_router(handover.router, prefix="/handover", tags=["handover"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(outreach.router, prefix="/outreach", tags=["outreach"])
api_router.include_router(qa.router, prefix="/qa", tags=["qa"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
