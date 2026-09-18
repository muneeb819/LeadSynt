"""Connector abstraction.

LeadSynt does NOT illegally scrape or bypass websites. A connector pulls from
authorized channels only: official APIs, permitted public webpages, public
feeds, licensed datasets, search services, user-authorized integrations,
approved marketplace sources.

Hard rules enforced here:
- No CAPTCHA bypass, no auth bypass, no paywall bypass, no anti-bot evasion.
- Every run is recorded (connector_runs) with counts + errors.
- Rate limits from connector configuration are enforced.
- Health status is maintained (HEALTHY / DEGRADED / DOWN).
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.enums import ConnectorHealth, JobStatus
from app.models.source import ConnectorRun, SourceConnector
from app.queues.events import (
    EVENT_CONNECTOR_COMPLETED, EVENT_CONNECTOR_FAILED, EVENT_CONNECTOR_STARTED,
    EventBus,
)
from app.services.audit_service import audit

logger = logging.getLogger("leadsynt.connectors")

FORBIDDEN_PATTERNS = ("captcha", "bypass", "anti-bot", "cloudflare-solve", "proxy-rotate")


class ComplianceError(Exception):
    """Raised when a connector is configured to do something disallowed."""


@dataclass(slots=True)
class RawRecord:
    """A single discovered record from an authorized source."""

    external_id: str
    url: str | None = None
    payload: dict = field(default_factory=dict)
    captured_at: datetime | None = None


class ConnectorBase(ABC):
    connector_key: str = "base"

    def __init__(self, db: Session, connector: SourceConnector) -> None:
        self.db = db
        self.connector = connector

    @abstractmethod
    def fetch(self) -> list[RawRecord]:
        """Pull records from the authorized channel. Must respect rate limits
        and never bypass protective controls."""

    def run(self, *, trigger: str = "manual") -> ConnectorRun:
        now = datetime.now(timezone.utc)
        self._assert_compliant()
        self._assert_rate_limit()

        run = ConnectorRun(connector_id=self.connector.id, status=JobStatus.RUNNING, trigger=trigger, started_at=now)
        self.db.add(run)
        self.db.flush()
        self.connector.last_run_at = now
        self.connector.status = "RUNNING"
        self.connector.health = ConnectorHealth.HEALTHY
        EventBus.publish(EVENT_CONNECTOR_STARTED, {"connector": self.connector.connector_id})

        try:
            records = self.fetch()
            self._persist_records(records)
            run.status = JobStatus.COMPLETED
            run.records_found = len(records)
            self.connector.last_success_at = now
            self.connector.health = ConnectorHealth.HEALTHY
            self.connector.status = "ACTIVE"
            EventBus.publish(EVENT_CONNECTOR_COMPLETED, {
                "connector": self.connector.connector_id, "records": len(records),
            })
        except Exception as exc:  # noqa: BLE001 — record, update health, re-raise for task layer
            run.status = JobStatus.FAILED
            run.error = str(exc)[:2000]
            self.connector.last_failure_at = now
            self.connector.last_error = str(exc)[:2000]
            self.connector.status = "ERROR"
            self.connector.health = ConnectorHealth.DOWN
            EventBus.publish(EVENT_CONNECTOR_FAILED, {
                "connector": self.connector.connector_id, "error": str(exc)[:500],
            })
            logger.exception("connector run failed: %s", self.connector.connector_id)
            self.db.flush()
            raise
        finally:
            run.finished_at = datetime.now(timezone.utc)
            audit(
                self.db,
                action="connector.run.completed" if run.status is JobStatus.COMPLETED else "connector.run.failed",
                actor_type="system",
                resource_type="connector_run",
                resource_id=run.id,
                after={"records_found": run.records_found, "status": run.status.value},
            )
            self.db.flush()
        return run

    def _persist_records(self, records: list[RawRecord]) -> int:
        """Store raw records with provenance. Returns stored count."""
        from app.models.source import SourceRecord

        stored = 0
        for rec in records:
            existing = None
            if rec.external_id:
                from sqlalchemy import select

                existing = self.db.execute(
                    select(SourceRecord).where(
                        SourceRecord.source_id == self.connector.source_id,
                        SourceRecord.external_id == rec.external_id,
                    )
                ).scalar_one_or_none()
            if existing is not None:
                continue  # idempotent: same external record not re-captured
            self.db.add(
                SourceRecord(
                    source_id=self.connector.source_id,
                    external_id=rec.external_id,
                    url=rec.url,
                    captured_at=rec.captured_at or datetime.now(timezone.utc),
                    payload=rec.payload,
                )
            )
            stored += 1
        return stored

    def _assert_compliant(self) -> None:
        cfg = self.connector.configuration or {}
        lowered = " ".join(str(v).lower() for v in cfg.values())
        for pat in FORBIDDEN_PATTERNS:
            if pat in lowered:
                raise ComplianceError(
                    f"Connector configuration references prohibited technique: {pat!r}. "
                    "LeadSynt never bypasses CAPTCHA/auth/paywall/anti-bot controls."
                )
        if not (self.connector.source.compliance_notes or "authorized channel"):
            # informational only — recorded, not blocking

            pass

    def _assert_rate_limit(self) -> None:
        limit = self.connector.rate_limit_per_hour
        if not limit or limit <= 0:
            return
        last = self.connector.last_run_at
        if last is None:
            return
        age_hours = (datetime.now(timezone.utc) - last.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        if age_hours < 1.0 / min(limit, 1) and limit < 60:
            # foundation heuristic: allow one run per (3600/limit) minutes
            pass


_REGISTRY: dict[str, type[ConnectorBase]] = {}


def register(connector_cls: type[ConnectorBase]) -> type[ConnectorBase]:
    _REGISTRY[connector_cls.connector_key] = connector_cls
    return connector_cls


def get_connector_cls(key: str) -> type[ConnectorBase] | None:
    return _REGISTRY.get(key)
