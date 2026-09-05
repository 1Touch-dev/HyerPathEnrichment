"""Feature flags are readable administration metadata with mutations disabled."""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.errors import AppError
from app.modules.admin.models import AdminAuditLog, FeatureFlag
from app.modules.admin.schemas import UpsertFeatureFlagRequest

pytestmark = pytest.mark.asyncio


async def _assert_upsert_rejected(db_session, superuser, key: str) -> None:
    from app.modules.admin.service import upsert_feature_flag

    with pytest.raises(AppError) as exc_info:
        await upsert_feature_flag(
            db_session,
            actor_id=superuser.id,
            key=key,
            payload=UpsertFeatureFlagRequest(enabled=True, value=None, description="test"),
            ip_address="127.0.0.1",
        )

    assert exc_info.value.status_code == 405
    assert exc_info.value.code == "FEATURE_FLAGS_READ_ONLY"


async def test_upsert_flag_is_rejected_without_create_or_success_audit(db_session, superuser):
    key = "test_flag_read_only"

    await _assert_upsert_rejected(db_session, superuser, key)

    flag = await db_session.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    assert flag.scalar_one_or_none() is None
    audit = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "feature_flag.flipped",
            AdminAuditLog.target_id == key,
        )
    )
    assert audit.scalars().all() == []


async def test_rejected_flip_preserves_existing_read_state(db_session, superuser, mock_redis):
    from app.modules.admin import repository

    key = "read_only_existing_probe"
    db_session.add(
        FeatureFlag(
            key=key,
            enabled=False,
            value={"variant": "control"},
            description="unchanged",
            updated_by=superuser.id,
        )
    )
    await db_session.commit()

    await _assert_upsert_rejected(db_session, superuser, key)

    persisted = await repository.get_feature_flag(db_session, key)
    assert persisted is not None
    assert persisted.enabled is False
    assert persisted.value == {"variant": "control"}
    assert persisted.description == "unchanged"
    assert not any(cache_key.startswith(f"admin:cache:{key}") for cache_key in mock_redis._kv)


async def test_repeated_upserts_remain_rejected_and_create_no_row(db_session, superuser):
    key = "repeated_read_only_probe"

    await _assert_upsert_rejected(db_session, superuser, key)
    await _assert_upsert_rejected(db_session, superuser, key)

    result = await db_session.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    assert result.scalar_one_or_none() is None
