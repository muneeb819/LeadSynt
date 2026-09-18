"""Analytics API — dashboard KPIs computed from REAL data."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_permission
from app.models.ai import AIRun
from app.models.enums import TicketStatus
from app.models.ops import JobRun
from app.models.source import SourceConnector
from app.models.ticket import Ticket, TicketStatus as TicketStatusRow
from app.schemas.common import Envelope

router = APIRouter()

LEAD_ZONE = {
    TicketStatus.QUALIFIED.value, TicketStatus.OUTREACH_READY.value,
    TicketStatus.OUTREACH_ACTIVE.value,
}
REPLY_ZONE = {TicketStatus.REPLIED.value, TicketStatus.HOT_LEAD.value}
CLOSED_WON = {TicketStatus.WON.value}
DEAL_STATUSES = {
    TicketStatus.NEGOTIATION.value, TicketStatus.PROPOSAL_SENT.value,
    TicketStatus.MEETING_BOOKED.value,
}


def _code_map(db: Session) -> dict[str, str]:
    return {r.id: r.code for r in db.execute(select(TicketStatusRow)).scalars()}


@router.get("/dashboard", response_model=Envelope)
def dashboard(user=Depends(require_permission("analytics:read")), db: Session = Depends(get_db)):
    codes = _code_map(db)
    now = datetime.now(timezone.utc)

    def count(statuses: set[str]) -> int:
        ids = [cid for cid, code in codes.items() if code in statuses]
        if not ids:
            return 0
        return db.execute(
            select(func.count()).select_from(Ticket).where(
                Ticket.status_id.in_(ids), Ticket.is_archived.is_(False)
            )
        ).scalar_one()

    by_status: Counter = Counter()
    for (tid,) in db.execute(select(Ticket.status_id)).all():
        by_status[codes.get(tid, "UNKNOWN")] += 1

    new_24h = db.execute(
        select(func.count()).select_from(Ticket)
        .where(Ticket.created_at >= now - timedelta(hours=24),
               Ticket.is_archived.is_(False))
    ).scalar_one()
    verified = db.execute(
        select(func.count()).select_from(Ticket).where(
            Ticket.verification_status == "VERIFIED", Ticket.is_archived.is_(False))
    ).scalar_one()
    avg_lead = db.execute(select(func.avg(Ticket.lead_score))).scalar() or 0

    # connector health
    connectors = db.execute(select(SourceConnector)).scalars().all()
    ai_failures = db.execute(
        select(func.count()).select_from(AIRun).where(AIRun.status == "FAILED")
    ).scalar_one()
    job_failures = db.execute(
        select(func.count()).select_from(JobRun).where(JobRun.status == "FAILED")
    ).scalar_one()

    return Envelope(data={
        "kpis": {
            "new_tickets_24h": new_24h,
            "verified_tickets": verified,
            "qualified_tickets": count(LEAD_ZONE),
            "hot_leads": count(REPLY_ZONE | {TicketStatus.AWAITING_HUMAN.value}),
            "replies": count(REPLY_ZONE),
            "open_deals": count(DEAL_STATUSES),
            "won_deals": count(CLOSED_WON),
            "avg_lead_score": round(float(avg_lead), 1),
        },
        "pipeline_by_status": {code: by_status.get(code, 0) for code in TicketStatus},
        "health": {
            "connectors": [
                {"connector_id": c.connector_id, "health": c.health.value} for c in connectors
            ],
            "connectors_total": len(connectors),
            "connectors_healthy": sum(1 for c in connectors if c.health.value == "HEALTHY"),
            "ai_runs_failed": ai_failures,
            "job_runs_failed": job_failures,
        },
        "generated_at": now.isoformat(),
    })
