"""Celery application.

Broker/backend: Redis. In dev without a worker, set
``LEADSynt_CELERY_TASK_ALWAYS_EAGER=true`` and tasks execute in-process —
same code path, no fakes.

Beat schedule (foundation):
- qa.sweep                hourly
- connectors.run_dev_feed every 6 hours
- tickets.refresh_freshness daily
- jobs.health_check       every 15 minutes
"""

from __future__ import annotations

from celery import Celery

from app.core.config import get_settings

s = get_settings()

celery = Celery(
    "leadsynt",
    broker=s.celery_broker_url,
    backend=s.celery_result_backend,
    include=["app.workers.tasks"],
)

celery.conf.update(
    task_always_eager=s.celery_task_always_eager,
    task_eager_propagates=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    timezone="UTC",
    beat_schedule={
        "qa-sweep-hourly": {
            "task": "leadsynt.qa.sweep",
            "schedule": 3600.0,
        },
        "connector-dev-feed": {
            "task": "leadsynt.connector.run",
            "schedule": 6 * 3600.0,
            "args": ("dev_feed",),
        },
        "tickets-refresh-freshness-daily": {
            "task": "leadsynt.tickets.refresh_freshness",
            "schedule": 24 * 3600.0,
        },
        "jobs-health-check": {
            "task": "leadsynt.health.check",
            "schedule": 15 * 60.0,
        },
    },
)
