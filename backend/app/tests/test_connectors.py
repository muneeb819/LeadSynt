"""Connector pipeline tests: authorized feed -> records -> tickets."""


def test_connector_run_creates_source_records(client, operator_headers, db_session):
    from pathlib import Path

    from app.core.database import SessionLocal
    from app.connectors.dev_feed import DevFeedConnector
    from app.models.enums import AuthMethod, SourceKind
    from app.models.source import Source, SourceConnector, SourceRecord
    from sqlalchemy import select

    # ensure feed file resolvable from backend cwd
    feed = Path("database/dev_feed.json")
    if not feed.exists():
        feed = Path(__file__).resolve().parents[3] / "database" / "dev_feed.json"
        assert feed.exists()

    db = SessionLocal()
    src = db.execute(select(Source).where(Source.name == "Approved Dev Marketplace Feed")).scalar_one_or_none()
    if src is None:
        src = Source(name="Approved Dev Marketplace Feed", platform="dev-marketplace",
                     kind=SourceKind.FEED, base_url="https://devmarket.example.com/feed",
                     compliance_notes="Authorized dev dataset")
        db.add(src)
        db.flush()
    conn = db.execute(select(SourceConnector).where(SourceConnector.connector_id == "dev_feed")).scalar_one_or_none()
    if conn is None:
        conn = SourceConnector(connector_id="dev_feed", source_id=src.id,
                               auth_method=AuthMethod.NONE,
                               configuration={"feed_path": str(feed)})
        db.add(conn)
        db.flush()
    # point connector at the feed we know exists
    conn.configuration = {"feed_path": str(feed), "channel": "authorized_local_file"}
    db.flush()

    runner = DevFeedConnector(db, conn)
    run = runner.run(trigger="test")
    records = db.execute(select(SourceRecord).where(
        SourceRecord.source_id == src.id, SourceRecord.is_consumed == False)).scalars().all()
    raw = [__import__("app.connectors.base", fromlist=["RawRecord"]).RawRecord(
        external_id=r.external_id or "", url=r.url, payload=r.payload,
        captured_at=r.captured_at) for r in records]
    created = runner.materialize(raw)
    run.tickets_created = created
    db.commit()

    assert run.status.value == "COMPLETED"
    assert run.records_found == 10
    assert created == 10
    # idempotent: second run creates no duplicates
    run2 = runner.run(trigger="test")
    db.commit()
    assert run2.records_found == 10
    # source records were not duplicated
    count = db.execute(select(SourceRecord.id).where(SourceRecord.source_id == src.id)).scalars().all()
    assert len(count) == 10
    # connector health recorded
    assert conn.health.value == "HEALTHY"
    assert conn.last_success_at is not None
    db.close()


def test_connector_compliance_guard_blocks_bypass_config(client, db_session):
    from app.connectors.base import ComplianceError
    from app.core.database import SessionLocal
    from app.models.enums import AuthMethod, SourceKind
    from app.models.source import Source, SourceConnector
    from sqlalchemy import select

    db = SessionLocal()
    src = Source(name="Evil Source", kind=SourceKind.PUBLIC_WEB,
                 compliance_notes="testing guard")
    db.add(src)
    db.flush()
    conn = SourceConnector(connector_id="evil", source_id=src.id,
                           auth_method=AuthMethod.NONE,
                           configuration={"captcha_solver": "auto-bypass"})
    db.add(conn)
    db.flush()
    runner = __import__("app.connectors.base", fromlist=["ConnectorBase"]).ConnectorBase
    class Dummy(runner):
        def fetch(self):
            return []
    d = Dummy(db, conn)
    try:
        d.run()
        raise AssertionError("expected ComplianceError")
    except ComplianceError as e:
        assert "captcha" in str(e).lower()
    db.close()
