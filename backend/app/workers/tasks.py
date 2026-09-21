"""Background tasks. Each task: own DB session, idempotent, auditable.

Tasks are the asynchronous half of the event-driven pipeline: scoring,
verification, connector runs, QA sweeps, freshness refresh.
"""

from __future__ import annotations

import logging

from app import core as _core
from app.core.config import get_settings
from app.workers.celery_app import celery

logger = logging.getLogger("leadsynt.workers")


def _session():
    # Resolved at call time so tests can redirect the session factory.
    return _core.database.SessionLocal()


@celery.task(name="leadsynt.health.check", bind=True)
def health_check(self) -> dict:
    """Liveness probe task: DB + Redis round-trip recorded as a job run."""
    from sqlalchemy import text

    from app.models.ops import Job, JobRun
    from app.models.enums import JobStatus
    from datetime import datetime, timezone

    db = _session()
    try:
        db.execute(text("SELECT 1"))
        result = {"db": "ok"}
        try:
            import redis as _redis

            client = _redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=1)
            client.ping()
            result["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            result["redis"] = f"unavailable: {exc.__class__.__name__}"
        job = db.query(Job).filter(Job.name == "health_check").first()
        if job is None:
            job = Job(name="health_check", description="DB/Redis liveness probe", is_enabled=True)
            db.add(job)
            db.flush()
        db.add(JobRun(job_id=job.id, status=JobStatus.COMPLETED,
                      started_at=datetime.now(timezone.utc),
                      finished_at=datetime.now(timezone.utc), result=result))
        db.commit()
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("health check failed")
        db.rollback()
        return {"status": "failed", "error": str(exc)}
    finally:
        db.close()


@celery.task(name="leadsynt.tickets.score", bind=True)
def score_ticket_task(self, ticket_id: str) -> dict:
    from app.services.scoring_service import score_ticket
    from app.services.ticket_service import get_ticket

    db = _session()
    try:
        ticket = get_ticket(db, ticket_id)
        result = score_ticket(db, ticket)
        db.commit()
        return {"ticket_id": ticket_id, **{k: result[k] for k in ("lead", "intent", "risk", "confidence")}}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("scoring failed for %s", ticket_id)
        raise
    finally:
        db.close()


@celery.task(name="leadsynt.verification.run", bind=True)
def verify_ticket_task(self, ticket_id: str) -> dict:
    from app.services.ticket_service import get_ticket
    from app.services.verification_service import verify_company, verify_email_address, verify_phone_number
    from app.models.contact import TicketContact, Contact
    from app.models.company import TicketCompany, Company
    from sqlalchemy import select

    db = _session()
    try:
        ticket = get_ticket(db, ticket_id)
        results: dict[str, str] = {}

        crows = db.execute(
            select(Contact).join(TicketContact, TicketContact.contact_id == Contact.id)
            .where(TicketContact.ticket_id == ticket_id)
        ).scalars().all()
        for c in crows:
            if c.work_email:
                rec = verify_email_address(db, email=c.work_email, ticket_id=ticket_id)
                results["email"] = rec.result.value
            if c.phone:
                rec = verify_phone_number(db, phone=c.phone, ticket_id=ticket_id)
                results["phone"] = rec.result.value
        crow = db.execute(
            select(Company).join(TicketCompany, TicketCompany.company_id == Company.id)
            .where(TicketCompany.ticket_id == ticket_id)
        ).scalars().first()
        if crow is not None:
            rec = verify_company(db, company_id=crow.id, ticket_id=ticket_id)
            results["company"] = rec.result.value

        from app.services.scoring_service import score_ticket

        score_ticket(db, ticket)
        db.commit()
        return {"ticket_id": ticket_id, "results": results, "verification_status": ticket.verification_status.value}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("verification failed for %s", ticket_id)
        raise
    finally:
        db.close()


@celery.task(name="leadsynt.connector.run", bind=True)
def run_connector_task(self, connector_key: str = "dev_feed", trigger: str = "scheduled") -> dict:
    from app.services.connector_service import run_connector

    db = _session()
    try:
        result = run_connector(db, connector_key=connector_key, trigger=trigger)
        db.commit()
        return result
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("connector task failed: %s", connector_key)
        raise
    finally:
        db.close()


@celery.task(name="leadsynt.qa.sweep", bind=True)
def qa_sweep_task(self, trigger: str = "scheduled") -> dict:
    from app.services.qa_service import run_qa_sweep

    db = _session()
    try:
        result = run_qa_sweep(db, trigger=trigger)
        db.commit()
        return result
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("qa sweep failed")
        raise
    finally:
        db.close()


@celery.task(name="leadsynt.tickets.refresh_freshness", bind=True)
def refresh_freshness_task(self) -> dict:
    from app.services.ticket_service import refresh_freshness

    s = get_settings()
    db = _session()
    try:
        changed = refresh_freshness(db, stale_hours=s.qa_stale_ticket_hours * 7)
        db.commit()
        return {"changed": changed}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("freshness refresh failed")
        raise
    finally:
        db.close()


@celery.task(name="leadsynt.outreach.send_due", bind=True)
def outreach_send_due_task(self) -> dict:
    """Deliver every due SCHEDULED outreach message through the full send-time
    gatechain. Called on a schedule; a message that fails a gate is marked
    BLOCKED (reason recorded + audited) and never silently skipped."""
    from app.outreach.service import run_due

    db = _session()
    try:
        result = run_due(db, actor_id=None, actor_type="system")
        db.commit()
        return result
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        logger.exception("outreach send-due failed")
        raise
    finally:
        db.close()
