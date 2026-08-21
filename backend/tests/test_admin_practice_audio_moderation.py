"""Admin practice-audio moderation endpoints: list/detail/moderate + RBAC gate
(migration 045, Admin Module Module 3 moderation layer). Mirrors
`test_admin_job_postings_moderation.py`'s shape.

Both `questions_router` and `practice_audio_router` are already permanently
wired into `app/modules/admin/__init__.py`'s aggregator (confirmed by reading
that file before writing this test), so no fixture-mounting boilerplate is
needed — this uses the `client` fixture from conftest directly, like any
other already-mounted admin router test.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select

from app.modules.admin.models import AdminAuditLog
from app.modules.sessions.models import PracticeAudioRecording, PracticeSession
from tests.envelope_helpers import assert_error, assert_success

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — see
# test_admin_rbac.py's comment; this repo's pyproject.toml sets
# asyncio_mode = "auto" already, and every test here is `async def`.


async def _make_practice_session(db_session, user_id) -> PracticeSession:
    session = PracticeSession(user_id=user_id, session_type="behavioral")
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


async def _make_recording(db_session, user_id, /, **overrides) -> PracticeAudioRecording:
    practice_session = await _make_practice_session(db_session, user_id)
    defaults = {
        "user_id": user_id,
        "practice_session_id": practice_session.id,
        "storage_path": f"/recordings/{uuid4().hex}.wav",
        "file_size_bytes": 1024,
        "audio_format": "wav",
    }
    defaults.update(overrides)
    recording = PracticeAudioRecording(**defaults)
    db_session.add(recording)
    await db_session.commit()
    await db_session.refresh(recording)
    return recording


async def test_list_practice_audio_requires_authentication(client):
    response = client.get("/api/admin/practice-audio")
    assert response.status_code == 401


async def test_list_practice_audio_regular_user_forbidden(client, regular_user, auth_headers):
    response = client.get("/api/admin/practice-audio", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_list_practice_audio_returns_cursor_shape(
    client, superuser, auth_headers, db_session
):
    await _make_recording(db_session, superuser.id)
    response = client.get("/api/admin/practice-audio", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert "items" in body and "next_cursor" in body and "has_more" in body
    assert len(body["items"]) >= 1


async def test_list_practice_audio_filters_by_moderation_status(
    client, superuser, auth_headers, db_session
):
    active = await _make_recording(db_session, superuser.id)
    hidden = await _make_recording(db_session, superuser.id, moderation_status="hidden")

    response = client.get(
        "/api/admin/practice-audio",
        params={"moderation_status": "hidden"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    ids = {item["id"] for item in body["items"]}
    assert str(hidden.id) in ids
    assert str(active.id) not in ids


async def test_get_practice_audio_detail(client, superuser, auth_headers, db_session):
    recording = await _make_recording(db_session, superuser.id)
    response = client.get(
        f"/api/admin/practice-audio/{recording.id}", headers=auth_headers(superuser.id)
    )
    body = assert_success(response)
    assert body["id"] == str(recording.id)
    assert body["moderation_status"] == "active"


async def test_get_practice_audio_detail_404(client, superuser, auth_headers):
    response = client.get(
        f"/api/admin/practice-audio/{uuid4()}", headers=auth_headers(superuser.id)
    )
    assert_error(response, 404)


async def test_moderate_practice_audio_happy_path(client, superuser, auth_headers, db_session):
    recording = await _make_recording(db_session, superuser.id)

    response = client.post(
        f"/api/admin/practice-audio/{recording.id}/moderate",
        json={"moderation_status": "hidden", "reason": "Inappropriate content"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert body["moderation_status"] == "hidden"
    assert body["moderated_by"] == str(superuser.id)
    assert body["moderated_at"] is not None

    await db_session.refresh(recording)
    assert recording.moderation_status == "hidden"
    assert recording.moderated_by == superuser.id
    assert recording.moderated_at is not None

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "practice_audio.moderate",
            AdminAuditLog.target_id == str(recording.id),
        )
    )
    entry = result.scalar_one()
    assert entry.actor_user_id == superuser.id
    assert entry.target_type == "practice_audio_recording"
    assert entry.before["moderation_status"] == "active"
    assert entry.after["moderation_status"] == "hidden"
    assert entry.after["reason"] == "Inappropriate content"


async def test_moderate_practice_audio_404(client, superuser, auth_headers):
    response = client.post(
        f"/api/admin/practice-audio/{uuid4()}/moderate",
        json={"moderation_status": "hidden", "reason": None},
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 404)


async def test_moderate_practice_audio_requires_moderate_permission_for_regular_user(
    client, regular_user, auth_headers, db_session
):
    recording = await _make_recording(db_session, regular_user.id)
    response = client.post(
        f"/api/admin/practice-audio/{recording.id}/moderate",
        json={"moderation_status": "hidden", "reason": None},
        headers=auth_headers(regular_user.id),
    )
    assert_error(response, 403)
