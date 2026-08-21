"""Feature flag CRUD, cache invalidation, audit trail (phase2_admin_module.md
§9.6)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_upsert_flag_creates_and_audits(db_session, superuser):
    from app.modules.admin.schemas import UpsertFeatureFlagRequest
    from app.modules.admin.service import upsert_feature_flag

    flag = await upsert_feature_flag(
        db_session,
        actor_id=superuser.id,
        key="test_flag",
        payload=UpsertFeatureFlagRequest(enabled=True, value=None, description="test"),
        ip_address="127.0.0.1",
    )
    assert flag.enabled is True

    from sqlalchemy import select

    from app.modules.admin.models import AdminAuditLog

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "feature_flag.flipped",
            AdminAuditLog.target_id == "test_flag",
        )
    )
    entry = result.scalar_one()
    assert entry.before is None  # first write for this key — no prior state
    assert entry.after == {"enabled": True, "value": None}


# INDIRECT (judgment call): §9.6's own sketch has NO body at all — just a
# docstring saying a flip "must not leave a stale cached read visible."
# Reading app/modules/admin/service.py's upsert_feature_flag and
# app/modules/admin/repository.py's list_feature_flags/get_feature_flag: this
# implementation has NO Redis caching layer in the feature-flag read path at
# all (unlike analytics.py, which explicitly uses cached_aggregate). Feature
# flag reads always hit the database directly, so there is no cache to
# invalidate and thus nothing that can ever go stale. The test below verifies
# both halves of that: (1) a flip is immediately visible via the actual read
# path used by flags_router.py, and (2) no admin:cache:* key is ever written
# for a feature-flag key (proving there is no hidden cache that COULD have
# gone stale). If a cache is added to this read path later, this test's
# second assertion will correctly start failing and must be revisited.
async def test_flip_invalidates_cache(db_session, superuser, mock_redis):
    from app.modules.admin import repository
    from app.modules.admin.schemas import UpsertFeatureFlagRequest
    from app.modules.admin.service import upsert_feature_flag

    key = "cache_invalidation_probe"

    await upsert_feature_flag(
        db_session,
        actor_id=superuser.id,
        key=key,
        payload=UpsertFeatureFlagRequest(enabled=False, value=None, description=None),
        ip_address="127.0.0.1",
    )
    first_read = await repository.get_feature_flag(db_session, key)
    assert first_read.enabled is False

    await upsert_feature_flag(
        db_session,
        actor_id=superuser.id,
        key=key,
        payload=UpsertFeatureFlagRequest(enabled=True, value={"variant": "b"}, description=None),
        ip_address="127.0.0.1",
    )
    second_read = await repository.get_feature_flag(db_session, key)
    assert second_read.enabled is True  # flip visible immediately, no stale read
    assert second_read.value == {"variant": "b"}

    assert not any(k.startswith(f"admin:cache:{key}") for k in mock_redis._kv)


async def test_upsert_flag_updates_existing_row_not_duplicate(db_session, superuser):
    from app.modules.admin import repository
    from app.modules.admin.schemas import UpsertFeatureFlagRequest
    from app.modules.admin.service import upsert_feature_flag

    key = "idempotent_upsert_probe"
    await upsert_feature_flag(
        db_session,
        actor_id=superuser.id,
        key=key,
        payload=UpsertFeatureFlagRequest(enabled=False, value=None, description="v1"),
        ip_address="127.0.0.1",
    )
    await upsert_feature_flag(
        db_session,
        actor_id=superuser.id,
        key=key,
        payload=UpsertFeatureFlagRequest(enabled=True, value=None, description="v2"),
        ip_address="127.0.0.1",
    )

    all_flags = await repository.list_feature_flags(db_session)
    matching = [f for f in all_flags if f.key == key]
    assert len(matching) == 1
    assert matching[0].description == "v2"
