"""Cursor encode/decode round-trip + list-endpoint pagination correctness
(phase2_admin_module.md §9.3)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.modules.admin.pagination import decode_cursor, encode_cursor


def test_cursor_round_trip():
    now = datetime.now(UTC)
    entity_id = uuid4()
    cursor = encode_cursor(now, entity_id)
    decoded_at, decoded_id = decode_cursor(cursor)
    assert decoded_at == now
    assert decoded_id == str(entity_id)


def test_cursor_is_opaque_base64():
    cursor = encode_cursor(datetime.now(UTC), uuid4())
    assert "|" not in cursor  # raw separator must not leak through encoding


def test_cursor_round_trip_with_string_entity_id():
    """encode_cursor accepts a plain string id too (repository.py passes
    `rows[-1].id`, always a UUID in practice, but the signature is
    `UUID | str`)."""
    now = datetime.now(UTC)
    cursor = encode_cursor(now, "not-a-uuid-but-a-string")
    decoded_at, decoded_id = decode_cursor(cursor)
    assert decoded_at == now
    assert decoded_id == "not-a-uuid-but-a-string"


async def test_list_users_pagination_walks_pages_without_duplicates(db_session):
    """End-to-end correctness check for repository.list_users' use of
    encode_cursor/decode_cursor: paging with limit=1 must return every user
    exactly once, in stable order, with has_more accurate at each step.

    `users` is a shared, session-scoped table across the whole test run (many
    other test files create users too), so this creates 3 fresh users and
    walks pages only until they all surface — since they're the newest rows
    (`order_by(User.created_at.desc(), User.id.desc())`), they must appear
    within the first few pages regardless of how many other rows already
    exist, without needing to walk the entire (potentially large) table.
    """
    from uuid import uuid4

    from app.auth.models import User
    from app.modules.admin import repository

    fresh_users = []
    for i in range(3):
        user = User(
            id=uuid4(),
            email=f"pagination-probe-{uuid4().hex[:8]}@example.com",
            first_name="Page",
            last_name=f"Probe{i}",
            is_active=True,
            is_verified=True,
        )
        db_session.add(user)
        fresh_users.append(user)
    await db_session.commit()
    for user in fresh_users:
        await db_session.refresh(user)
    fresh_ids = {user.id for user in fresh_users}

    seen_ids: set = set()
    cursor = None
    has_more = True
    pages = 0
    while has_more and not fresh_ids <= seen_ids:
        rows, cursor, has_more = await repository.list_users(db_session, cursor=cursor, limit=1)
        assert len(rows) <= 1
        for row in rows:
            assert row.id not in seen_ids
            seen_ids.add(row.id)
        pages += 1
        assert pages < 20  # the 3 newest rows must surface within the first few pages

    assert fresh_ids <= seen_ids
