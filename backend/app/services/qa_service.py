"""QA Master — deterministic inspection engine (foundation).

Read-only inspection; produces findings with severity, evidence, root-cause
hypothesis, recommended action, affected component and test recommendation.
QA Master NEVER mutates business data. Code/config/DB changes go through the
change-request pipeline (change_requests) with human approval.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.ai import AIRun
from app.models.enums import (
    ConnectorHealth, DuplicateStatus, FindingSeverity, FindingStatus,
    JobStatus, QATrigger, TicketStatus, VerificationStatus,
)
from app.models.ops import JobRun, WebhookEvent
from app.models.qa import QAFinding, QARun
from app.models.source import SourceConnector
from app.models.ticket import Ticket, TicketStatus as TicketStatusRow
from app.queues.events import EVENT_QA_FINDING_CREATED, EventBus
from app.services.audit_service import audit

logger = logging.getLogger("leadsynt.qa")

ACTIVE_STATUSES = {
    TicketStatus.DISCOVERED.value, TicketStatus.INGESTED.value,
    TicketStatus.PROCESSING.value, TicketStatus.VERIFICATION_PENDING.value,
    TicketStatus.VERIFIED.value, TicketStatus.QUALIFIED.value,
    TicketStatus.OUTREACH_READY.value, TicketStatus.OUTREACH_ACTIVE.value,
}


def _status_ids(db: Session, codes: set[str]) -> list[str]:
    return list(
        db.execute(select(TicketStatusRow.id).where(TicketStatusRow.code.in_(codes))).scalars()
    )


def _add_finding(
    db: Session, run_id: str, *, category: str, severity: FindingSeverity, title: str,
    description: str, evidence: dict, root_cause: str, action: str,
    component: str, test_rec: str,
) -> QAFinding:
    f = QAFinding(
        run_id=run_id, category=category, severity=severity, title=title,
        description=description, evidence=evidence,
        root_cause_hypothesis=root_cause, recommended_action=action,
        affected_component=component, test_recommendation=test_rec,
        status=FindingStatus.OPEN,
    )
    db.add(f)
    EventBus.publish(EVENT_QA_FINDING_CREATED, {"category": category, "severity": severity.value, "title": title})
    return f


def run_qa_sweep(db: Session, *, trigger: str = "manual", actor_id: str | None = None) -> dict:
    s = get_settings()
    now = datetime.now(timezone.utc)
    run = QARun(
        trigger=QATrigger(trigger.upper() if trigger.upper() in ("MANUAL", "SCHEDULED", "WEBHOOK") else "MANUAL"),
        started_at=now, status="RUNNING",
    )
    db.add(run)
    db.flush()
    counts: Counter = Counter()

    # 1. Stale tickets ---------------------------------------------------------
    stale_hours = s.qa_stale_ticket_hours
    stale_before = now - timedelta(hours=stale_hours)
    active_ids = _status_ids(db, set(ACTIVE_STATUSES))
    stale = db.execute(
        select(Ticket).where(
            Ticket.status_id.in_(active_ids),
            Ticket.discovered_at.isnot(None),
            Ticket.discovered_at < stale_before,
            Ticket.is_archived.is_(False),
        )
    ).scalars().all()
    if stale:
        _add_finding(
            db, run.id, category="data_quality", severity=FindingSeverity.MEDIUM,
            title=f"{len(stale)} active ticket(s) older than {stale_hours}h without progress",
            description="Active tickets whose discovery timestamp exceeds the staleness threshold.",
            evidence={"count": len(stale),
                      "samples": [{"id": t.id, "reference": t.reference,
                                   "discovered_at": t.discovered_at.isoformat() if t.discovered_at else None} for t in stale[:5]]},
            root_cause="Discovery pipeline created tickets but downstream processing/outreach did not advance them.",
            action="Review stale tickets; resume processing or mark EXPIRED.",
            component="pipeline", test_rec="test_qa_stale_ticket_detection",
        )
        counts["stale_tickets"] = len(stale)

    # 2. Unresolved duplicates ---------------------------------------------------
    dups = db.execute(
        select(Ticket).where(
            Ticket.duplicate_status.in_([DuplicateStatus.POSSIBLE_DUPLICATE, DuplicateStatus.DUPLICATE]),
            Ticket.is_archived.is_(False),
        )
    ).scalars().all()
    if dups:
        _add_finding(
            db, run.id, category="duplicates", severity=FindingSeverity.MEDIUM if any(
                t.duplicate_status is DuplicateStatus.DUPLICATE for t in dups
            ) else FindingSeverity.LOW,
            title=f"{len(dups)} ticket(s) flagged as duplicate/possible-duplicate",
            description="Dedup flags that have not been resolved (merge or dismiss).",
            evidence={"count": len(dups),
                      "samples": [{"id": t.id, "reference": t.reference,
                                   "status": t.duplicate_status.value} for t in dups[:5]]},
            root_cause="Duplicate detection raised flags; entity resolution / human review pending.",
            action="Run Entity Resolution review; merge or dismiss each flag.",
            component="entity-resolution", test_rec="test_duplicate_detection",
        )
        counts["duplicates"] = len(dups)

    # 3. Verification failures -----------------------------------------------------
    failed_ver = db.execute(
        select(Ticket).where(Ticket.verification_status == VerificationStatus.FAILED,
                             Ticket.is_archived.is_(False))
    ).scalars().all()
    if failed_ver:
        _add_finding(
            db, run.id, category="verification", severity=FindingSeverity.HIGH,
            title=f"{len(failed_ver)} ticket(s) with FAILED verification",
            description="Tickets whose latest verification result failed (e.g., disposable email).",
            evidence={"count": len(failed_ver),
                      "samples": [{"id": t.id, "reference": t.reference} for t in failed_ver[:5]]},
            root_cause="Source data quality: contact details failed deterministic verification.",
            action="Re-verify with corrected data or DISQUALIFY after review.",
            component="verification", test_rec="test_verification_email",
        )
        counts["verification_failures"] = len(failed_ver)

    # 4. Connector health ---------------------------------------------------------
    bad_connectors = db.execute(
        select(SourceConnector).where(
            (SourceConnector.health == ConnectorHealth.DOWN) | (SourceConnector.status == "ERROR")
        )
    ).scalars().all()
    if bad_connectors:
        _add_finding(
            db, run.id, category="connectors", severity=FindingSeverity.HIGH,
            title=f"{len(bad_connectors)} connector(s) DOWN or in ERROR state",
            description="Connectors whose latest run failed or whose health is DOWN.",
            evidence={"samples": [{"connector_id": c.connector_id, "last_error": (c.last_error or "")[:200]}
                                  for c in bad_connectors[:5]]},
            root_cause="Upstream source unavailable, credential expired, or rate-limited.",
            action="Inspect last_error, rotate credentials, and re-run the connector.",
            component="connectors", test_rec="test_connector_run_bookkeeping",
        )
        counts["connector_failures"] = len(bad_connectors)

    # 5. AI run failures -------------------------------------------------------------
    failed_runs = db.execute(
        select(AIRun).where(AIRun.status == "FAILED").order_by(AIRun.created_at.desc()).limit(20)
    ).scalars().all()
    if failed_runs:
        _add_finding(
            db, run.id, category="ai", severity=FindingSeverity.MEDIUM,
            title=f"{len(failed_runs)} recent AI run(s) failed",
            description="AI runs with status FAILED in the recent window.",
            evidence={"samples": [{"run_id": r.id, "agent": r.agent_id,
                                   "error": (r.error or "")[:200]} for r in failed_runs[:5]]},
            root_cause="Provider error, schema validation failure, or cost cap exceeded.",
            action="Review errors; fix prompt/schema or provider config, then re-run.",
            component="ai-agents", test_rec="test_ai_run_recording",
        )
        counts["ai_failures"] = len(failed_runs)

    # 6. Failed jobs ------------------------------------------------------------------
    failed_jobs = db.execute(
        select(JobRun).where(JobRun.status == JobStatus.FAILED)
    ).scalars().all()
    if failed_jobs:
        _add_finding(
            db, run.id, category="jobs", severity=FindingSeverity.MEDIUM,
            title=f"{len(failed_jobs)} background job run(s) failed",
            description="Job runs that ended in FAILED status.",
            evidence={"samples": [{"run_id": r.id, "error": (r.error or "")[:200]} for r in failed_jobs[:5]]},
            root_cause="Worker error, dependency outage (Redis/DB), or task bug.",
            action="Inspect worker logs and re-enqueue idempotent jobs.",
            component="workers", test_rec="test_worker_task_execution",
        )
        counts["failed_jobs"] = len(failed_jobs)

    # 7. Failed webhook events ---------------------------------------------------------
    bad_wh = db.execute(
        select(WebhookEvent).where(WebhookEvent.status == "FAILED").order_by(WebhookEvent.received_at.desc()).limit(20)
    ).scalars().all()
    if bad_wh:
        _add_finding(
            db, run.id, category="webhooks", severity=FindingSeverity.MEDIUM,
            title=f"{len(bad_wh)} webhook event(s) failed processing",
            description="Inbound webhooks that failed (signature or processing).",
            evidence={"samples": [{"id": w.id, "source": w.source, "error": (w.error or "")[:200]}
                                  for w in bad_wh[:5]]},
            root_cause="Misconfigured shared secret, malformed payload, or unknown ticket id.",
            action="Verify sender configuration and payload contract.",
            component="webhooks", test_rec="test_webhook_signature",
        )
        counts["webhook_failures"] = len(bad_wh)

    # 8. Unscored tickets -----------------------------------------------------------------
    unscored = db.execute(
        select(Ticket).where(
            Ticket.lead_score.is_(None),
            Ticket.status_id.in_([
                sid for sid, code in db.execute(select(TicketStatusRow.id, TicketStatusRow.code)).all()
                if code in (TicketStatus.PROCESSING.value, TicketStatus.VERIFIED.value, TicketStatus.QUALIFIED.value)
            ]),
            Ticket.is_archived.is_(False),
        )
    ).scalars().all()
    if unscored:
        _add_finding(
            db, run.id, category="scoring", severity=FindingSeverity.MEDIUM,
            title=f"{len(unscored)} ticket(s) in active pipeline without scores",
            description="Tickets that should carry scores but have no lead_score.",
            evidence={"samples": [{"id": t.id, "reference": t.reference} for t in unscored[:5]]},
            root_cause="Scoring task did not run for these tickets.",
            action="Enqueue leadsynt.tickets.score for affected tickets.",
            component="scoring", test_rec="test_scoring_snapshots",
        )
        counts["unscored"] = len(unscored)

    # 9. Handover zone without owner --------------------------------------------------------
    ownerless = db.execute(
        select(Ticket).where(
            Ticket.owner_id.is_(None),
            Ticket.status_id.in_(_status_ids(db, {
                TicketStatus.REPLIED.value, TicketStatus.HOT_LEAD.value,
                TicketStatus.OUTREACH_ACTIVE.value,
            })),
            Ticket.is_archived.is_(False),
        )
    ).scalars().all()
    if ownerless:
        _add_finding(
            db, run.id, category="handover", severity=FindingSeverity.HIGH,
            title=f"{len(ownerless)} ticket(s) in reply/outreach zone with NO owner",
            description="Handover notifications would go nowhere; these tickets need an assigned user.",
            evidence={"samples": [{"id": t.id, "reference": t.reference} for t in ownerless[:5]]},
            root_cause="Ticket created/advanced without owner assignment.",
            action="Assign owners immediately; make owner mandatory for OUTREACH transitions.",
            component="crm", test_rec="test_handover_notification",
        )
        counts["ownerless_handover_zone"] = len(ownerless)

    # 10. Data spikes (simple 24h vs 7d baseline) ---------------------------------------------
    created_24h = db.execute(
        select(func.count()).select_from(Ticket)
        .where(Ticket.created_at >= now - timedelta(hours=24))
    ).scalar_one()
    created_7d = db.execute(
        select(func.count()).select_from(Ticket)
        .where(Ticket.created_at >= now - timedelta(days=7))
    ).scalar_one()
    baseline_per_day = created_7d / 7.0
    if baseline_per_day >= 5 and created_24h > 5 * baseline_per_day:
        _add_finding(
            db, run.id, category="spikes", severity=FindingSeverity.INFO,
            title=f"Ticket creation spike: {created_24h} in 24h vs baseline ~{baseline_per_day:.1f}/day",
            description="Volume significantly above the 7-day baseline.",
            evidence={"created_24h": created_24h, "created_7d": created_7d},
            root_cause="Connector backfill, duplicate source run, or legitimate market surge.",
            action="Check connector_runs for duplicate captures; review new ticket quality.",
            component="discovery", test_rec="test_duplicate_detection",
        )
        counts["spike"] = created_24h

    run.status = "COMPLETED"
    run.finished_at = datetime.now(timezone.utc)
    run.metrics = dict(counts)
    run.summary = (
        f"QA sweep complete: {sum(counts.values())} signal(s) across "
        f"{len(counts)} categor{'y' if len(counts) == 1 else 'ies'}. "
        + (", ".join(f"{k}={v}" for k, v in counts.items()) or "system healthy.")
    )
    audit(db, action="qa.run.completed", actor_id=actor_id,
          actor_type="user" if actor_id else "system",
          resource_type="qa_run", resource_id=run.id, after={"counts": dict(counts)})
    db.flush()
    return {"qa_run_id": run.id, "counts": dict(counts), "summary": run.summary}
