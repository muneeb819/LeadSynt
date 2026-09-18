# SQL Server backup & restore (runbook)

## Nightly backup (cron on the app host, 02:00)

```bash
BACKUP DATABASE [LeadSynt]
TO DISK = '/var/backups/leadsynt/leadsynt_$(date +\%F).bak'
WITH COMPRESSION, INIT, STATS = 10;
```

Rotate 14 days local + copy to object storage (see `../../infrastructure/`
storage container) via `AZCOPY` or the cloud provider's tooling. Verify each
backup with `RESTORE VERIFYONLY`.

## Restore (disaster recovery)

1. Stop API + worker (drain queues; Celery results in Redis are disposable —
   jobs are re-runnable).
2. Provision a fresh SQL Server 2022 instance (compose or Terraform).
3. `RESTORE DATABASE [LeadSynt] FROM DISK = '<backup>' WITH REPLACE;`
4. `alembic current` must report the latest revision — if not, run
   `alembic upgrade head` BEFORE starting the app.
5. Start services; `GET /api/v1/health/ready` must return `ready`.
6. Run `tests/e2e/foundation_check.py` against the restored instance.
7. Document RTO/RPO achieved in the incident record.

Target: RPO ≤ 24 h (nightly backup), RTO ≤ 2 h.
