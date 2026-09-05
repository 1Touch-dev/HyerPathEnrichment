"""Tests for the atomic weighted sliding-window rate limit algorithm.

Covers ``sliding_window_params`` (the pure math core) and ``check_rate_limit``
(the behavioral contract), plus a structural sanity check on the Lua script
itself so a future edit can't silently regress the algorithm without a test
failing.

The autouse ``fake_redis`` fixture in ``conftest.py`` patches
``app.dependencies.rate_limit.get_redis_client`` (not
``app.infrastructure.redis.get_redis_client``), and ``check_rate_limit``
takes its Redis client as an explicit argument rather than looking one up
itself. So here we request the ``fake_redis: FakeRedis`` fixture directly and
pass it straight into ``check_rate_limit`` -- this is both simpler and more
robust than relying on the module-level patch, and it avoids ever touching a
real (unreachable, in this environment) Redis connection.
"""

from __future__ import annotations

import time

import pytest

from app.infrastructure.redis import _RATE_LIMIT_SCRIPT, check_rate_limit, sliding_window_params
from tests.conftest import FakeRedis

# ---------------------------------------------------------------------------
# 1-4: pure unit tests of sliding_window_params (no mocking, no Redis)
# ---------------------------------------------------------------------------


def test_sliding_window_params_at_window_start():
    """Right at a window boundary, elapsed=0 so the previous window is fully weighted."""
    window_id, weight = sliding_window_params(120.0, 60)
    assert window_id == 2
    assert weight == 1.0


def test_sliding_window_params_at_window_end():
    """Just before the next boundary, elapsed~=window_seconds so weight decays to ~0."""
    window_id, weight = sliding_window_params(179.999, 60)
    assert window_id == 2
    assert weight == pytest.approx(0.0, abs=1e-3)


def test_sliding_window_params_at_midpoint():
    """Halfway through the window, the previous window is weighted at exactly half."""
    window_id, weight = sliding_window_params(150.0, 60)
    assert window_id == 2
    assert weight == pytest.approx(0.5)


def test_sliding_window_params_window_id_rolls_over_at_boundary():
    """window_id increments cleanly at exact multiples of window_seconds, not before."""
    assert sliding_window_params(119.999, 60)[0] == 1
    assert sliding_window_params(120.0, 60)[0] == 2


# ---------------------------------------------------------------------------
# 5: basic behavioral sanity of check_rate_limit
# ---------------------------------------------------------------------------


async def test_check_rate_limit_allows_under_limit_blocks_at_limit(
    monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis
):
    """First `limit` calls succeed, the next one is blocked.

    Time is pinned mid-window so the test can't flake by straddling a real
    window boundary between calls.
    """
    monkeypatch.setattr(time, "time", lambda: 1_000_000.0)

    assert await check_rate_limit(fake_redis, "testscope", limit=3) is True
    assert await check_rate_limit(fake_redis, "testscope", limit=3) is True
    assert await check_rate_limit(fake_redis, "testscope", limit=3) is True
    assert await check_rate_limit(fake_redis, "testscope", limit=3) is False


# ---------------------------------------------------------------------------
# 6: the core boundary-burst fix, demonstrated concretely
# ---------------------------------------------------------------------------


async def test_check_rate_limit_boundary_burst_is_throttled(
    monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis
):
    """A client that fills window N right at its end can't get a fresh full
    allotment the instant window N+1 begins.

    window_seconds=60, limit=5, window_id=100 (t0=6000..6060).

    Phase 1 -- fill window N (id=100) right at its end, t0 = 100*60 + 59.9 = 6059.9:
      sliding_window_params(6059.9, 60) -> window_id=100, elapsed=59.9,
      weight = 1 - 59.9/60 = 0.0016666...
      previous key (ratelimit:testscope:99) was never written -> previous=0,
      so previous*weight contributes nothing here; each of the 5 calls just
      checks its own running `current` (0,1,2,3,4), all < limit=5, so all 5
      succeed and window 100's counter ends at exactly 5.

    Phase 2 -- the exact instant window N+1 begins, t1 = 101*60 + 0 = 6060.0:
      sliding_window_params(6060.0, 60) -> window_id=101, elapsed=0,
      weight = 1 - 0/60 = 1.0 (previous window fully counted -- we just
      arrived, so none of it has "aged out" yet).
      current key (ratelimit:testscope:101) is fresh -> current=0.
      previous key (ratelimit:testscope:100) = 5 (from phase 1).
      estimated = current + previous*weight = 0 + 5*1.0 = 5.0
      estimated (5.0) >= limit (5) -> BLOCKED.
      So the very first call in the new window is already blocked: 0 of the
      "fresh" limit=5 leaked through, in sharp contrast to a naive fixed
      window, which would have handed out a full new allotment of 5 at this
      exact instant (a momentary 2x burst: 5 at the end of window N plus 5 at
      the start of window N+1).

    Phase 3 -- a little further into window N+1, t2 = 101*60 + 6 = 6066.0:
      sliding_window_params(6066.0, 60) -> window_id=101 (unchanged),
      elapsed=6, weight = 1 - 6/60 = 0.9.
      current=0 (still, since phase 2's call was blocked and did not
      increment), previous=5.
      estimated = 0 + 5*0.9 = 4.5 < 5 -> ALLOWED (current becomes 1).
      Next call: current=1, estimated = 1 + 4.5 = 5.5 >= 5 -> BLOCKED.
      So even 6 seconds (10%) into the new window, at most 1 of the 5
      "fresh" slots opens up -- nowhere near the full limit=5 a naive fixed
      window would have granted immediately at the boundary.
    """
    window_seconds = 60
    limit = 5
    window_id = 100

    # Phase 1: fill window N to the limit right at its tail end.
    monkeypatch.setattr(time, "time", lambda: window_id * window_seconds + 59.9)
    for _ in range(limit):
        assert await check_rate_limit(fake_redis, "burstscope", limit, window_seconds) is True

    # Phase 2: the exact instant window N+1 opens -- already fully blocked.
    monkeypatch.setattr(time, "time", lambda: (window_id + 1) * window_seconds + 0.0)
    assert await check_rate_limit(fake_redis, "burstscope", limit, window_seconds) is False

    # Phase 3: 6s (10%) into window N+1 -- only 1 of the 5 "fresh" slots has opened up.
    monkeypatch.setattr(time, "time", lambda: (window_id + 1) * window_seconds + 6.0)
    assert await check_rate_limit(fake_redis, "burstscope", limit, window_seconds) is True
    assert await check_rate_limit(fake_redis, "burstscope", limit, window_seconds) is False


# ---------------------------------------------------------------------------
# 7: contrast test -- windows far apart don't blend together
# ---------------------------------------------------------------------------


async def test_check_rate_limit_far_future_window_gets_fresh_allotment(
    monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis
):
    """Only the immediately-preceding window is ever blended in.

    A window 5 windows later has a "previous" key of (new_window_id - 1),
    which is a different, never-written key (reads as 0 regardless of
    `weight`), so a full fresh limit is available -- old windows don't leak
    forward indefinitely.
    """
    window_seconds = 60
    limit = 5
    window_id = 100

    monkeypatch.setattr(time, "time", lambda: window_id * window_seconds + 59.9)
    for _ in range(limit):
        assert await check_rate_limit(fake_redis, "farscope", limit, window_seconds) is True
    # Window N is now full; the very next call in the same window is blocked.
    assert await check_rate_limit(fake_redis, "farscope", limit, window_seconds) is False

    # Jump 5 full windows into the future. previous_key = ratelimit:farscope:104,
    # which was never written, so previous=0 no matter the weight.
    future_window_id = window_id + 5
    monkeypatch.setattr(time, "time", lambda: future_window_id * window_seconds + 1.0)
    for _ in range(limit):
        assert await check_rate_limit(fake_redis, "farscope", limit, window_seconds) is True
    assert await check_rate_limit(fake_redis, "farscope", limit, window_seconds) is False


# ---------------------------------------------------------------------------
# 8: static sanity check on the actual Lua script string
# ---------------------------------------------------------------------------


def test_rate_limit_script_structure_has_not_regressed():
    """Loose structural check that the Lua script still implements the
    weighted-estimate-then-atomic-increment algorithm.

    Kept as substring checks (not a full Lua parser) so it stays robust to
    unrelated cosmetic edits (whitespace, comments) while still failing if
    the atomicity or the core estimate/compare logic is accidentally changed.
    """
    assert "redis.call('GET', KEYS[1]" in _RATE_LIMIT_SCRIPT
    assert "redis.call('GET', KEYS[2]" in _RATE_LIMIT_SCRIPT
    assert "redis.call('INCR', KEYS[1]" in _RATE_LIMIT_SCRIPT
    assert "redis.call('EXPIRE', KEYS[1]" in _RATE_LIMIT_SCRIPT
    assert "estimated >= limit" in _RATE_LIMIT_SCRIPT
    # The read-estimate-then-write sequence must stay in a single script so
    # it executes atomically server-side; this file doesn't shell out to
    # more than one eval() per check_rate_limit call, which is what makes
    # that guarantee hold.
    assert _RATE_LIMIT_SCRIPT.count("redis.call") == 4


# ---------------------------------------------------------------------------
# 9: different scopes are independent
# ---------------------------------------------------------------------------


async def test_check_rate_limit_scopes_are_independent(
    monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis
):
    """Exhausting one scope's limit must not affect a different scope."""
    monkeypatch.setattr(time, "time", lambda: 2_000_000.0)

    for _ in range(2):
        assert await check_rate_limit(fake_redis, "scope-a", limit=2) is True
    # scope-a is now exhausted.
    assert await check_rate_limit(fake_redis, "scope-a", limit=2) is False

    # scope-b, same limit, must still have its own full allotment.
    assert await check_rate_limit(fake_redis, "scope-b", limit=2) is True
    assert await check_rate_limit(fake_redis, "scope-b", limit=2) is True
    assert await check_rate_limit(fake_redis, "scope-b", limit=2) is False
