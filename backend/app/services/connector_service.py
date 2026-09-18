"""Connector run service — shared by the API (on-demand) and Celery (beat).

One implementation, two entry points. The run is idempotent per external
record id and fully bookkept (connector_runs + connector health).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import RawRecord, get_connector_cls
from app.core.exceptions import NotFoundError
from app.models.source import ConnectorRun, SourceConnector, SourceRecord

logger = logging.getLogger("leadsynt.connectors")


def run_connector(db: Session, *, connector_key: str, trigger: str = "manual") -> dict[str, Any]:
    connector = db.execute(
        select(SourceConnector).where(SourceConnector.connector_id == connector_key)
    ).scalar_one_or_none()
    if connector is None:
        raise NotFoundError(f"Connector not registered: {connector_key}")
    cls = get_connector_cls(connector_key)
    if cls is None:
        return {"status": "skipped", "reason": f"no implementation registered for {connector_key}"}

    runner = cls(db, connector)
    run = runner.run(trigger=trigger)

    created = 0
    if hasattr(runner, "materialize") and run.status is not None:
        records = db.execute(
            select(SourceRecord).where(
                SourceRecord.source_id == connector.source_id,
                SourceRecord.is_consumed.is_(False),
            )
        ).scalars().all()
        raw = [
            RawRecord(external_id=r.external_id or "", url=r.url,
                      payload=r.payload, captured_at=r.captured_at)
            for r in records
        ]
        created = runner.materialize(raw)
        run.tickets_created = created
    db.flush()
    return {
        "connector": connector_key,
        "status": run.status.value if run.status else "FAILED",
        "records_found": run.records_found,
        "tickets_created": created,
        "error": run.error,
    }
