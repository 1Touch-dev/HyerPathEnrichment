from __future__ import annotations

import asyncio
import csv
import io
import time
from typing import Any

from app.core.config import get_settings
from app.enrichers.base import Enricher
from app.domain.enrichment import EnrichmentRequest
from app.clients.sidecar import SidecarClient


class LocalBusinessEnricher(Enricher):
    source_name = "Google Maps Scraper"

    async def validate(self, request: EnrichmentRequest) -> bool:
        return bool(request.business)

    async def _fetch(self, request: EnrichmentRequest) -> dict[str, Any]:
        settings = get_settings()
        client = SidecarClient(settings.gmaps_scraper_url, timeout=60.0)
        if not client.enabled:
            return {}

        created = await client.post_json(
            "/api/v1/jobs",
            json={
                "name": "hyrepath-enrich",
                "keywords": [request.business],
                "depth": 1,
                "lang": "en",
                "max_time": 180_000_000_000,
            },
        )
        if not isinstance(created, dict) or "id" not in created:
            return {}

        job_id = str(created["id"])
        deadline = time.monotonic() + settings.gmaps_job_timeout_seconds
        terminal = False
        while time.monotonic() < deadline:
            status = await client.get_json(f"/api/v1/jobs/{job_id}")
            if not isinstance(status, dict):
                return {}
            state = str(status.get("Status", status.get("status", ""))).lower()
            if state in {"ok", "completed", "done"}:
                terminal = True
                break
            if state in {"failed", "error"}:
                return {}
            await asyncio.sleep(settings.gmaps_job_poll_seconds)

        if not terminal:
            return {}

        csv_text = await client.get_text(f"/api/v1/jobs/{job_id}/download")
        record = self._first_csv_row(csv_text)
        if record is None:
            return {}

        return {
            "business": {
                "name": str(record.get("title") or record.get("name") or request.business),
                "address": str(record.get("address") or record.get("complete_address") or ""),
                "website": str(record.get("website") or record.get("link") or ""),
                "rating": float(record.get("review_rating") or record.get("rating") or 0.0),
                "phone": str(record.get("phone") or record.get("phone_number") or ""),
                "metadata": {"provider": self.source_name, "job_id": job_id},
            }
        }

    def _first_csv_row(self, csv_text: str | None) -> dict[str, str] | None:
        if not csv_text or not csv_text.strip():
            return None
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            if row:
                return {str(key): str(value) for key, value in row.items() if key}
        return None
