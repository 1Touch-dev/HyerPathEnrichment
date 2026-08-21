"""Admin interview-question moderation endpoints: list/detail/moderate + RBAC
gate (migration 045, Admin Module Module 3 moderation layer). Mirrors
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

from app.models import InterviewQuestion
from app.modules.admin.models import AdminAuditLog
from tests.envelope_helpers import assert_error, assert_success

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — see
# test_admin_rbac.py's comment; this repo's pyproject.toml sets
# asyncio_mode = "auto" already, and every test here is `async def`.


async def _make_question(db_session, /, **overrides) -> InterviewQuestion:
    defaults = {
        "question_text": "Tell me about a time you resolved a conflict.",
        "question_category": "behavioral",
        "difficulty": "medium",
        "job_roles": ["backend_engineer"],
        "technologies": ["python"],
        "source": "seed",
    }
    defaults.update(overrides)
    question = InterviewQuestion(**defaults)
    db_session.add(question)
    await db_session.commit()
    await db_session.refresh(question)
    return question


async def test_list_questions_requires_authentication(client):
    response = client.get("/api/admin/questions")
    assert response.status_code == 401


async def test_list_questions_regular_user_forbidden(client, regular_user, auth_headers):
    response = client.get("/api/admin/questions", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_list_questions_returns_cursor_shape(client, superuser, auth_headers, db_session):
    await _make_question(db_session)
    response = client.get("/api/admin/questions", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert "items" in body and "next_cursor" in body and "has_more" in body
    assert len(body["items"]) >= 1


async def test_list_questions_filters_by_moderation_status(
    client, superuser, auth_headers, db_session
):
    active = await _make_question(db_session)
    hidden = await _make_question(db_session, moderation_status="hidden")

    response = client.get(
        "/api/admin/questions",
        params={"moderation_status": "hidden"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    ids = {item["id"] for item in body["items"]}
    assert str(hidden.id) in ids
    assert str(active.id) not in ids


async def test_get_question_detail(client, superuser, auth_headers, db_session):
    question = await _make_question(db_session)
    response = client.get(f"/api/admin/questions/{question.id}", headers=auth_headers(superuser.id))
    body = assert_success(response)
    assert body["id"] == str(question.id)
    assert body["moderation_status"] == "active"


async def test_get_question_detail_404(client, superuser, auth_headers):
    response = client.get(f"/api/admin/questions/{uuid4()}", headers=auth_headers(superuser.id))
    assert_error(response, 404)


async def test_moderate_question_happy_path(client, superuser, auth_headers, db_session):
    question = await _make_question(db_session)

    response = client.post(
        f"/api/admin/questions/{question.id}/moderate",
        json={"moderation_status": "hidden", "reason": "Low quality"},
        headers=auth_headers(superuser.id),
    )
    body = assert_success(response)
    assert body["moderation_status"] == "hidden"
    assert body["moderated_by"] == str(superuser.id)
    assert body["moderated_at"] is not None

    await db_session.refresh(question)
    assert question.moderation_status == "hidden"
    assert question.moderated_by == superuser.id
    assert question.moderated_at is not None

    result = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "questions.moderate",
            AdminAuditLog.target_id == str(question.id),
        )
    )
    entry = result.scalar_one()
    assert entry.actor_user_id == superuser.id
    assert entry.target_type == "interview_question"
    assert entry.before["moderation_status"] == "active"
    assert entry.after["moderation_status"] == "hidden"
    assert entry.after["reason"] == "Low quality"


async def test_moderate_question_404(client, superuser, auth_headers):
    response = client.post(
        f"/api/admin/questions/{uuid4()}/moderate",
        json={"moderation_status": "hidden", "reason": None},
        headers=auth_headers(superuser.id),
    )
    assert_error(response, 404)


async def test_moderate_question_requires_moderate_permission_for_regular_user(
    client, regular_user, auth_headers, db_session
):
    question = await _make_question(db_session)
    response = client.post(
        f"/api/admin/questions/{question.id}/moderate",
        json={"moderation_status": "hidden", "reason": None},
        headers=auth_headers(regular_user.id),
    )
    assert_error(response, 403)
