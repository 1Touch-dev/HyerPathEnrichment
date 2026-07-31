from __future__ import annotations

import asyncio
import csv
import io
import json
import time
from typing import Any

from app.clients.sidecar import SidecarClient
from app.core.config import get_settings
from app.domain.enrichment import EnrichmentRequest
from app.enrichers.base import Enricher


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
                "max_time": 180000,  # milliseconds: 180 seconds = 3 minutes
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

        return self._parse_business_record(record, request, job_id)

    def _first_csv_row(self, csv_text: str | None) -> dict[str, str] | None:
        if not csv_text or not csv_text.strip():
            return None
        reader = csv.DictReader(io.StringIO(csv_text))
        for row in reader:
            if row:
                return {str(key): str(value) for key, value in row.items() if key}
        return None

    def _parse_business_record(
        self, record: dict[str, str], request: EnrichmentRequest, job_id: str
    ) -> dict[str, Any]:
        """Parse CSV record into enriched BusinessProfile."""

        # Helper to safely parse int
        def parse_int(value: str | None) -> int | None:
            if not value or value == "":
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        # Helper to safely parse float
        def parse_float(value: str | None) -> float | None:
            if not value or value == "":
                return None
            try:
                return float(value)
            except (ValueError, TypeError):
                return None

        # Helper to parse JSON-like fields
        def parse_json(value: str | None) -> Any:
            if not value or value == "":
                return None
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return value  # Return as string if not valid JSON

        # Helper to parse comma-separated lists
        def parse_list(value: str | None) -> list[str] | None:
            if not value or value == "":
                return None
            return [item.strip() for item in value.split(",") if item.strip()]

        return {
            "business": {
                # Core fields
                "name": str(record.get("title") or record.get("name") or request.business),
                "address": str(record.get("address") or ""),
                "website": str(record.get("website") or ""),
                "rating": parse_float(record.get("review_rating")) or 0.0,
                "phone": str(record.get("phone") or ""),
                # Location & identification
                "category": record.get("category"),
                "latitude": parse_float(record.get("latitude")),
                "longitude": parse_float(record.get("longitude")),
                "place_id": record.get("place_id"),
                "cid": record.get("cid"),
                "plus_code": record.get("plus_code"),
                "complete_address": record.get("complete_address"),
                # Operations
                "open_hours": record.get("open_hours"),
                "popular_times": record.get("popular_times"),
                "timezone": record.get("timezone"),
                "status": record.get("status"),
                # Reviews & ratings
                "review_count": parse_int(record.get("review_count")),
                "reviews_per_rating": parse_json(record.get("reviews_per_rating")),
                "reviews_link": record.get("reviews_link"),
                "user_reviews": parse_json(record.get("user_reviews")),
                # Media
                "thumbnail": record.get("thumbnail"),
                "images": parse_list(record.get("images")),
                "street_view_url": record.get("street_view_url"),
                # Commerce
                "price_range": record.get("price_range"),
                "reservations": record.get("reservations"),
                "order_online": record.get("order_online"),
                "menu": record.get("menu"),
                "credit_cards_accepted": record.get("credit_cards_accepted"),
                # Additional info
                "description": record.get("descriptions"),  # Note: "descriptions" in CSV
                "about": record.get("about"),
                "owner": record.get("owner"),
                "emails": parse_list(record.get("emails")),
                # Google Maps references
                "link": record.get("link"),
                "data_id": record.get("data_id"),
                "metadata": {
                    "provider": self.source_name,
                    "job_id": job_id,
                    "input_id": record.get("input_id"),
                },
            }
        }
