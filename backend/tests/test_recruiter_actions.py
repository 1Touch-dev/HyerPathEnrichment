"""HTTP tests for the recruiter_actions router endpoints (Machine 2, Track 09).

`recruiter_actions.router` is not registered in `app/main.py` yet — main.py is
being edited concurrently by several sibling tracks in this same working
directory, so registration is deferred to a later integration phase (mirrors
`test_interview_scheduling_router.py`'s own note about the same situation). To
exercise the real HTTP surface without touching `app/main.py`, this test
module mounts both of this track's routers onto the already-built `app`
instance at import time.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.main import app, current_verified_user
from app.modules.documents.models import CandidateDocument
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.recruiter_actions.models import PendingRecruiterAction, RoleSuggestion
from app.modules.recruiter_actions.router import router as recruiter_actions_router
from app.modules.recruiter_actions.router import users_router as recruiter_actions_users_router
from tests.envelope_helpers import assert_error, assert_success

if not any(getattr(route, "path", "").startswith("/api/recruiter-actions") for route in app.routes):
    app.include_router(recruiter_actions_router, dependencies=[Depends(current_verified_user)])
if not any(
    getattr(route, "path", "") == "/api/users/me/recruiter-action-mode" for route in app.routes
):
    app.include_router(
        recruiter_actions_users_router, dependencies=[Depends(current_verified_user)]
    )

# Deliberately reuse conftest.py's default `client` fixture (a plain
# TestClient(app), no `with` block) rather than redefining a local one that
# enters/exits the app's lifespan context per test. Entering/exiting lifespan
# on every test function opens an extra ad hoc startup db session against the
# same shared engine/pool as this file's own `db` fixture, which was observed
# to corrupt a pooled SQLite connection for a later `db.expire_all()` +
# `db.execute(select(...))` pair in this same test run (MissingGreenlet from
# a connection left in a bad state) — unrelated to this track's business
# logic, but avoided here by not invoking lifespan repeatedly.


def _auth_headers(user_id: str | None = None) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": user_id or str(uuid4()),
    }


async def _refetch_job_match(match_id) -> JobMatch:
    """Query via a brand-new session rather than reusing the fixture's `db`
    session with `expire_all()` — reusing the same session after an HTTP call
    triggered an unrelated MissingGreenlet error against this repo's current
    aiosqlite/SQLAlchemy pin in this exact test shape; a fresh session avoids it."""
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        result = await session.execute(select(JobMatch).where(JobMatch.id == match_id))
        return result.scalar_one()


async def _refetch_user(user_id) -> User:
    from app.database.session import SessionLocal

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one()


async def _make_user(db: AsyncSession, **overrides: Any) -> User:
    user_id = overrides.pop("id", uuid4())
    defaults: dict[str, Any] = {
        "id": user_id,
        "email": f"recruiter-actions-{user_id.hex[:10]}@example.com",
        "first_name": "Test",
        "last_name": "User",
        "is_active": True,
        "is_verified": True,
    }
    defaults.update(overrides)
    user = User(**defaults)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_job_match(db: AsyncSession, candidate: User) -> JobMatch:
    posting = JobPosting(
        dedup_key=f"dedup-{uuid4().hex}",
        title="Backend Engineer",
        company="Acme Corp",
        location="Remote",
        remote=True,
        source="linkedin",
        source_url="https://example.com/job",
    )
    db.add(posting)
    await db.commit()
    await db.refresh(posting)

    match = JobMatch(
        user_id=candidate.id,
        job_posting_id=posting.id,
        similarity_score=0.8,
        rule_score=0.7,
        overall_score=75.0,
        score_breakdown={"salary_fit": 1.0},
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


async def _make_processed_document(db: AsyncSession, candidate: User) -> CandidateDocument:
    document = CandidateDocument(
        user_id=candidate.id,
        document_type="cv",
        original_filename="resume.pdf",
        storage_path=f"/tmp/{uuid4().hex}.pdf",
        file_hash=uuid4().hex,
        file_size_bytes=1024,
        processing_status="completed",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


@pytest.fixture
async def candidate_autonomous(db: AsyncSession) -> User:
    return await _make_user(db, recruiter_action_mode="autonomous")


@pytest.fixture
async def candidate_approval_required(db: AsyncSession) -> User:
    """Explicit approval_required, distinct from the untouched-default case
    exercised separately below."""
    return await _make_user(db, recruiter_action_mode="approval_required")


@pytest.fixture
async def recruiter(db: AsyncSession) -> User:
    return await _make_user(db)


# ---------------------------------------------------------------------------
# POST /api/recruiter-actions/apply
# ---------------------------------------------------------------------------


async def test_apply_autonomous_mode_applies_immediately(
    client: TestClient, db: AsyncSession, candidate_autonomous: User, recruiter: User
) -> None:
    match = await _make_job_match(db, candidate_autonomous)
    headers = _auth_headers(str(recruiter.id))

    response = client.post(
        "/api/recruiter-actions/apply",
        headers=headers,
        json={"candidate_user_id": str(candidate_autonomous.id), "job_match_id": str(match.id)},
    )
    data = assert_success(response)
    assert data["mode"] == "autonomous"
    assert data["status"] == "applied"

    refreshed = await _refetch_job_match(match.id)
    assert refreshed.application_status == "applied"
    assert refreshed.applied_at is not None

    pending_result = await db.execute(
        select(PendingRecruiterAction).where(PendingRecruiterAction.job_match_id == match.id)
    )
    assert pending_result.scalar_one_or_none() is None


async def test_apply_approval_required_creates_pending_action_without_touching_job_match(
    client: TestClient, db: AsyncSession, candidate_approval_required: User, recruiter: User
) -> None:
    match = await _make_job_match(db, candidate_approval_required)
    headers = _auth_headers(str(recruiter.id))

    response = client.post(
        "/api/recruiter-actions/apply",
        headers=headers,
        json={
            "candidate_user_id": str(candidate_approval_required.id),
            "job_match_id": str(match.id),
        },
    )
    data = assert_success(response)
    assert data["mode"] == "approval_required"
    assert data["status"] == "pending"
    assert data["pending_action"]["status"] == "pending"

    result = await db.execute(select(JobMatch).where(JobMatch.id == match.id))
    refreshed = result.scalar_one()
    assert refreshed.application_status == "new"
    assert refreshed.applied_at is None

    pending_result = await db.execute(
        select(PendingRecruiterAction).where(PendingRecruiterAction.job_match_id == match.id)
    )
    pending = pending_result.scalar_one()
    assert pending.status == "pending"
    assert pending.candidate_user_id == candidate_approval_required.id
    assert pending.recruiter_user_id == recruiter.id


async def test_apply_default_mode_is_approval_required(
    client: TestClient, db: AsyncSession, recruiter: User
) -> None:
    """A candidate who never touched recruiter_action_mode gets the
    conservative default — release-blocking boundary for this track."""
    candidate = await _make_user(db)  # no recruiter_action_mode override
    assert candidate.recruiter_action_mode == "approval_required"
    match = await _make_job_match(db, candidate)
    headers = _auth_headers(str(recruiter.id))

    response = client.post(
        "/api/recruiter-actions/apply",
        headers=headers,
        json={"candidate_user_id": str(candidate.id), "job_match_id": str(match.id)},
    )
    data = assert_success(response)
    assert data["mode"] == "approval_required"

    result = await db.execute(select(JobMatch).where(JobMatch.id == match.id))
    refreshed = result.scalar_one()
    assert refreshed.application_status == "new"


# ---------------------------------------------------------------------------
# POST /api/recruiter-actions/pending/{id}/approve|reject
# ---------------------------------------------------------------------------


async def test_approve_pending_action_by_non_candidate_403s(
    client: TestClient, db: AsyncSession, candidate_approval_required: User, recruiter: User
) -> None:
    match = await _make_job_match(db, candidate_approval_required)
    await _make_processed_document(db, candidate_approval_required)
    apply_response = client.post(
        "/api/recruiter-actions/apply",
        headers=_auth_headers(str(recruiter.id)),
        json={
            "candidate_user_id": str(candidate_approval_required.id),
            "job_match_id": str(match.id),
        },
    )
    action_id = assert_success(apply_response)["pending_action"]["id"]

    other_user = await _make_user(db)
    response = client.post(
        f"/api/recruiter-actions/pending/{action_id}/approve",
        headers=_auth_headers(str(other_user.id)),
    )
    assert_error(response, 403)


async def test_approve_pending_action_happy_path_updates_job_match(
    client: TestClient, db: AsyncSession, candidate_approval_required: User, recruiter: User
) -> None:
    match = await _make_job_match(db, candidate_approval_required)
    await _make_processed_document(db, candidate_approval_required)
    apply_response = client.post(
        "/api/recruiter-actions/apply",
        headers=_auth_headers(str(recruiter.id)),
        json={
            "candidate_user_id": str(candidate_approval_required.id),
            "job_match_id": str(match.id),
        },
    )
    action_id = assert_success(apply_response)["pending_action"]["id"]

    response = client.post(
        f"/api/recruiter-actions/pending/{action_id}/approve",
        headers=_auth_headers(str(candidate_approval_required.id)),
    )
    data = assert_success(response)
    assert data["status"] == "approved"

    refreshed = await _refetch_job_match(match.id)
    assert refreshed.application_status == "applied"
    assert refreshed.applied_at is not None


async def test_approve_pending_action_without_processed_cv_409s(
    client: TestClient, db: AsyncSession, candidate_approval_required: User, recruiter: User
) -> None:
    match = await _make_job_match(db, candidate_approval_required)
    # Deliberately no processed CandidateDocument for this candidate.
    apply_response = client.post(
        "/api/recruiter-actions/apply",
        headers=_auth_headers(str(recruiter.id)),
        json={
            "candidate_user_id": str(candidate_approval_required.id),
            "job_match_id": str(match.id),
        },
    )
    action_id = assert_success(apply_response)["pending_action"]["id"]

    response = client.post(
        f"/api/recruiter-actions/pending/{action_id}/approve",
        headers=_auth_headers(str(candidate_approval_required.id)),
    )
    assert_error(response, 409)


async def test_approve_already_decided_action_409s(
    client: TestClient, db: AsyncSession, candidate_approval_required: User, recruiter: User
) -> None:
    match = await _make_job_match(db, candidate_approval_required)
    await _make_processed_document(db, candidate_approval_required)
    apply_response = client.post(
        "/api/recruiter-actions/apply",
        headers=_auth_headers(str(recruiter.id)),
        json={
            "candidate_user_id": str(candidate_approval_required.id),
            "job_match_id": str(match.id),
        },
    )
    action_id = assert_success(apply_response)["pending_action"]["id"]
    candidate_headers = _auth_headers(str(candidate_approval_required.id))

    first = client.post(
        f"/api/recruiter-actions/pending/{action_id}/approve", headers=candidate_headers
    )
    assert_success(first)

    second = client.post(
        f"/api/recruiter-actions/pending/{action_id}/approve", headers=candidate_headers
    )
    assert_error(second, 409)


async def test_reject_already_rejected_action_409s(
    client: TestClient, db: AsyncSession, candidate_approval_required: User, recruiter: User
) -> None:
    match = await _make_job_match(db, candidate_approval_required)
    apply_response = client.post(
        "/api/recruiter-actions/apply",
        headers=_auth_headers(str(recruiter.id)),
        json={
            "candidate_user_id": str(candidate_approval_required.id),
            "job_match_id": str(match.id),
        },
    )
    action_id = assert_success(apply_response)["pending_action"]["id"]
    candidate_headers = _auth_headers(str(candidate_approval_required.id))

    first = client.post(
        f"/api/recruiter-actions/pending/{action_id}/reject", headers=candidate_headers
    )
    assert_success(first)

    second = client.post(
        f"/api/recruiter-actions/pending/{action_id}/reject", headers=candidate_headers
    )
    assert_error(second, 409)


# ---------------------------------------------------------------------------
# POST /api/recruiter-actions/suggest + respond
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", ["autonomous", "approval_required"])
async def test_suggest_role_always_creates_suggestion_regardless_of_mode(
    client: TestClient, db: AsyncSession, recruiter: User, mode: str
) -> None:
    candidate = await _make_user(db, recruiter_action_mode=mode)
    match = await _make_job_match(db, candidate)

    response = client.post(
        "/api/recruiter-actions/suggest",
        headers=_auth_headers(str(recruiter.id)),
        json={"candidate_user_id": str(candidate.id), "job_match_id": str(match.id)},
    )
    data = assert_success(response)
    assert data["status"] == "pending"

    result = await db.execute(select(RoleSuggestion).where(RoleSuggestion.job_match_id == match.id))
    suggestion = result.scalar_one()
    assert suggestion.candidate_user_id == candidate.id
    assert suggestion.status == "pending"


async def test_respond_to_suggestion_accept(
    client: TestClient, db: AsyncSession, candidate_approval_required: User, recruiter: User
) -> None:
    match = await _make_job_match(db, candidate_approval_required)
    suggest_response = client.post(
        "/api/recruiter-actions/suggest",
        headers=_auth_headers(str(recruiter.id)),
        json={
            "candidate_user_id": str(candidate_approval_required.id),
            "job_match_id": str(match.id),
        },
    )
    suggestion_id = assert_success(suggest_response)["id"]

    response = client.post(
        f"/api/recruiter-actions/suggestions/{suggestion_id}/respond",
        headers=_auth_headers(str(candidate_approval_required.id)),
        json={"accept": True},
    )
    data = assert_success(response)
    assert data["status"] == "accepted"


# ---------------------------------------------------------------------------
# GET /api/recruiter-actions/pending, /suggestions — scoped to caller only
# ---------------------------------------------------------------------------


async def test_list_pending_actions_never_returns_another_candidates_rows(
    client: TestClient, db: AsyncSession, recruiter: User
) -> None:
    candidate_a = await _make_user(db)
    candidate_b = await _make_user(db)
    match_a = await _make_job_match(db, candidate_a)
    match_b = await _make_job_match(db, candidate_b)

    client.post(
        "/api/recruiter-actions/apply",
        headers=_auth_headers(str(recruiter.id)),
        json={"candidate_user_id": str(candidate_a.id), "job_match_id": str(match_a.id)},
    )
    client.post(
        "/api/recruiter-actions/apply",
        headers=_auth_headers(str(recruiter.id)),
        json={"candidate_user_id": str(candidate_b.id), "job_match_id": str(match_b.id)},
    )

    response = client.get(
        "/api/recruiter-actions/pending", headers=_auth_headers(str(candidate_a.id))
    )
    data = assert_success(response)
    assert len(data) == 1
    assert data[0]["candidate_user_id"] == str(candidate_a.id)


async def test_list_suggestions_never_returns_another_candidates_rows(
    client: TestClient, db: AsyncSession, recruiter: User
) -> None:
    candidate_a = await _make_user(db)
    candidate_b = await _make_user(db)
    match_a = await _make_job_match(db, candidate_a)
    match_b = await _make_job_match(db, candidate_b)

    client.post(
        "/api/recruiter-actions/suggest",
        headers=_auth_headers(str(recruiter.id)),
        json={"candidate_user_id": str(candidate_a.id), "job_match_id": str(match_a.id)},
    )
    client.post(
        "/api/recruiter-actions/suggest",
        headers=_auth_headers(str(recruiter.id)),
        json={"candidate_user_id": str(candidate_b.id), "job_match_id": str(match_b.id)},
    )

    response = client.get(
        "/api/recruiter-actions/suggestions", headers=_auth_headers(str(candidate_b.id))
    )
    data = assert_success(response)
    assert len(data) == 1
    assert data[0]["candidate_user_id"] == str(candidate_b.id)


# ---------------------------------------------------------------------------
# PATCH /api/users/me/recruiter-action-mode
# ---------------------------------------------------------------------------


async def test_update_recruiter_action_mode_happy_path(
    client: TestClient, db: AsyncSession, candidate_approval_required: User
) -> None:
    response = client.patch(
        "/api/users/me/recruiter-action-mode",
        headers=_auth_headers(str(candidate_approval_required.id)),
        json={"recruiter_action_mode": "autonomous"},
    )
    data = assert_success(response)
    assert data["recruiter_action_mode"] == "autonomous"

    refreshed = await _refetch_user(candidate_approval_required.id)
    assert refreshed.recruiter_action_mode == "autonomous"


async def test_update_recruiter_action_mode_rejects_invalid_value(
    client: TestClient, candidate_approval_required: User
) -> None:
    response = client.patch(
        "/api/users/me/recruiter-action-mode",
        headers=_auth_headers(str(candidate_approval_required.id)),
        json={"recruiter_action_mode": "some_invalid_value"},
    )
    assert_error(response, 422, "VALIDATION_ERROR")
