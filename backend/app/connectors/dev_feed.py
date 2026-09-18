"""Authorized demo feed connector.

Demonstrates the full DISCOVERY -> INGESTION pipeline end-to-end using a
LOCAL, EXPLICITLY AUTHORIZED data file (``database/dev_feed.json``) — a
stand-in for a licensed/official feed. It proves: connector run bookkeeping,
rate limits, raw-record provenance, ticket creation, dedup, scoring, audit.

This is the only connector shipped in the foundation; real marketplace /
API connectors are later phases behind the same abstraction.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.connectors.base import ConnectorBase, RawRecord, register


@register
class DevFeedConnector(ConnectorBase):
    """Reads an authorized local JSON feed file. No network, no bypasses."""

    connector_key = "dev_feed"

    FEED_PATH = Path("database/dev_feed.json")

    def fetch(self) -> list[RawRecord]:
        path = self.FEED_PATH
        if not path.exists():
            # fall back to the project-root-relative location when cwd differs
            alt = Path(__file__).resolve().parents[3] / "database" / "dev_feed.json"
            if alt.exists():
                path = alt
            else:
                raise FileNotFoundError(
                    f"dev feed file not found: {path} — see scripts/make_dev_feed.py"
                )
        data = json.loads(path.read_text(encoding="utf-8"))
        now = datetime.now(timezone.utc)
        records: list[RawRecord] = []
        for item in data.get("items", []):
            records.append(
                RawRecord(
                    external_id=str(item.get("external_id")),
                    url=item.get("url"),
                    payload=item,
                    captured_at=now,
                )
            )
        return records

    def materialize(self, records: list[RawRecord]) -> int:
        """Turn raw records into tickets (deduplicated by external id)."""
        from sqlalchemy import select

        from app.models.source import SourceRecord
        from app.services.ticket_service import create_ticket

        created = 0
        for rec in records:
            existing = self.db.execute(
                select(SourceRecord).where(
                    SourceRecord.source_id == self.connector.source_id,
                    SourceRecord.external_id == rec.external_id,
                )
            ).scalar_one_or_none()
            if existing is not None and existing.is_consumed:
                continue
            p = rec.payload
            ticket_data = {
                "type_code": p.get("type_code", "MARKET_OPPORTUNITY"),
                "type_name": p.get("type_name", "Market Opportunity"),
                "domain": p.get("domain"),
                "market_sector": p.get("market_sector"),
                "product": p.get("product"),
                "service": p.get("service"),
                "requirement": p.get("requirement"),
                "intent_level": p.get("intent_level"),
                "urgency": p.get("urgency"),
                "budget": p.get("budget"),
                "currency": p.get("currency"),
                "location": p.get("location"),
                "jurisdiction": p.get("jurisdiction"),
                "pain_point": p.get("pain_point"),
                "platform": p.get("platform") or self.connector.source.platform,
                "platform_url": p.get("url"),
                "original_url": p.get("url"),
                "official_website_url": p.get("official_website"),
                "discovered_by": self.connector.connector_id,
                "company": p.get("company"),
                "contact": p.get("contact"),
                "source_id": self.connector.source_id,
            }
            create_ticket(
                self.db, data=ticket_data,
                actor_type="system", actor_id=self.connector.connector_id,
            )
            created += 1
            if existing is not None:
                existing.is_consumed = True
        self.db.flush()
        return created
