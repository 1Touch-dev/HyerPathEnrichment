"""Cursor pagination helper. See Decision 4 — Stripe-style opaque cursor over
(created_at, id), never bare offsets, for every new admin list endpoint."""

from __future__ import annotations

import base64
from datetime import datetime
from uuid import UUID


def encode_cursor(created_at: datetime, entity_id: UUID | str) -> str:
    raw = f"{created_at.isoformat()}|{entity_id}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    raw = base64.urlsafe_b64decode(cursor.encode()).decode()
    created_at_str, entity_id = raw.split("|", 1)
    return datetime.fromisoformat(created_at_str), entity_id
