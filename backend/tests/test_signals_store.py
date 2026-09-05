"""Direct unit tests for app.signals.store (bypassing the HTTP layer).

These call `create_signal`/`list_signals` directly against the `db` fixture's
session so behavior (and coverage) isn't dependent on how the ASGI test
client happens to schedule the request.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.signals.store import create_signal, list_signals


@pytest.mark.asyncio
async def test_create_signal_persists_and_returns_list_item(db: AsyncSession) -> None:
    item = await create_signal(
        db,
        watch_id="watch-direct-1",
        title="Direct Signal",
        url="https://direct.example",
        timestamp="2026-01-01T00:00:00Z",
    )

    assert item.watch_id == "watch-direct-1"
    assert item.title == "Direct Signal"
    assert item.url == "https://direct.example"
    assert item.source == "changedetection"
    assert item.id.startswith("sig_")


@pytest.mark.asyncio
async def test_list_signals_returns_persisted_items_with_total(db: AsyncSession) -> None:
    await create_signal(
        db,
        watch_id="watch-direct-2",
        title="Second Signal",
        url="https://direct2.example",
    )

    items, total = await list_signals(db, limit=10, offset=0)

    assert total >= 1
    assert any(item.watch_id == "watch-direct-2" for item in items)
    assert len(items) <= 10


@pytest.mark.asyncio
async def test_list_signals_clamps_limit_and_offset(db: AsyncSession) -> None:
    await create_signal(
        db, watch_id="watch-direct-3", title="Clamp Signal", url="https://direct3.example"
    )

    items, total = await list_signals(db, limit=9999, offset=-5)

    assert total >= 1
    assert isinstance(items, list)
