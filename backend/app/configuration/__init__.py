"""Dynamic (database-backed) configuration.

Static config (secrets, URLs) lives in environment variables.
Operator-tunable config (thresholds, schedules, rules) lives in
``system_settings`` and is admin-editable via /api/v1/settings — avoiding
hardcoded values administrators should control (spec §24).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ops import SystemSetting

DEFAULTS: dict[str, dict[str, Any]] = {
    "scoring": {
        "qualification_threshold": 70,
        "hot_lead_threshold": 85,
        "description": "Lead score thresholds for qualification / hot-lead flags",
    },
    "verification": {
        "stale_after_days": 30,
        "disposable_domain_blocklist_source": "built-in",
        "description": "Verification policy",
    },
    "outreach": {
        "max_daily_per_contact": 1,
        "quiet_hours": {"start": "20:00", "end": "09:00"},
        "require_suppression_check": True,
        "description": "Outreach guardrails (suppression check is mandatory)",
    },
    "retention": {
        "archived_ticket_days": 365,
        "audit_log_days": 730,
        "description": "Data retention policy (GDPR/PDPA-aligned)",
    },
    "qa": {
        "stale_ticket_hours": 168,
        "max_open_findings_before_alert": 20,
        "description": "QA Master thresholds",
    },
}


def ensure_defaults(db: Session) -> None:
    existing = {s.key for s in db.execute(select(SystemSetting)).scalars()}
    for key, val in DEFAULTS.items():
        if key not in existing:
            db.add(
                SystemSetting(
                    key=key,
                    value={k: v for k, v in val.items() if k != "description"},
                    description=val.get("description"),
                )
            )
    db.flush()


def get_setting(db: Session, key: str, default: Any = None) -> Any:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None or row.value is None:
        return default
    return row.value


def set_setting(db: Session, key: str, value: Any, updated_by: str | None = None) -> SystemSetting:
    row = db.execute(select(SystemSetting).where(SystemSetting.key == key)).scalar_one_or_none()
    if row is None:
        row = SystemSetting(key=key, value=value, updated_by=updated_by)
        db.add(row)
    else:
        row.value = value
        row.updated_by = updated_by
    db.flush()
    return row


def list_settings(db: Session) -> list[SystemSetting]:
    return list(db.execute(select(SystemSetting).order_by(SystemSetting.key)).scalars())
