"""HTTP + repository tests for recruiter-candidate assignment
(machine-2-parallel-tracks/08-recruiter-candidate-assignment.md).

`assignment_router` is registered in `app/main.py` as `recruiter_assignments_router`
(added during the Machine 1 six-track reconciliation, since no track's own
dependency table originally listed `main.py` as an RA edit target).

Release-blocking focus (see docs/adr/0019-tenancy-model.md Decision Section 4):
`RecruiterCandidateAssignment` must never be used as an access-control gate.
`test_zero_assignment_rows_does_not_block_candidate_scoped_endpoint` below is
the explicit regression guard for that invariant, using
`POST /api/recruiter-actions/suggest` (already registered in main.py) as the
pre-existing candidate-scoped endpoint that takes an arbitrary
`candidate_user_id` and lets any recruiter act on it.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.modules.brands import repository as assignment_repository
from app.modules.brands.models import RecruiterCandidateAssignment
from app.modules.job_matching.models import JobMatch, JobPosting
from tests.envelope_helpers import assert_error, assert_success

# Deliberately reuse conftest.py's default `client` fixture (plain
# TestClient(app), no lifespan context) -- see test_recruiter_actions.py's own
# comment for why a locally redefined lifespan-entering `client` fixture is
# avoided here.


def _auth_headers(user_id: str) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": user_id,
    }


async def _make_user(db: AsyncSession, **overrides: Any) -> User:
    user_id = overrides.pop("id", uuid4())
    defaults: dict[str, Any] = {
        "id": user_id,
        "email": f"ra-test-{user_id.hex[:10]}@example.com",
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


@pytest.fixture
async def recruiter_a(db: AsyncSession) -> User:
    from app.modules.admin.models import Role

    result = await db.execute(select(Role).where(Role.name == "recruiter"))
    recruiter_role = result.scalar_one()
    return await _make_user(db, role_id=recruiter_role.id)


@pytest.fixture
async def recruiter_b(db: AsyncSession) -> User:
    from app.modules.admin.models import Role

    result = await db.execute(select(Role).where(Role.name == "recruiter"))
    recruiter_role = result.scalar_one()
    return await _make_user(db, role_id=recruiter_role.id)


@pytest.fixture
async def candidate(db: AsyncSession) -> User:
    return await _make_user(db)


# ---------------------------------------------------------------------------
# 1. RELEASE-BLOCKING: RecruiterCandidateAssignment must never gate access.
# See docs/adr/0019-tenancy-model.md Decision Section 4.
# ---------------------------------------------------------------------------


async def test_zero_assignment_rows_does_not_block_candidate_scoped_endpoint(
    client: TestClient, db: AsyncSession, recruiter_a: User, candidate: User
) -> None:
    """Recruiter A has NO `RecruiterCandidateAssignment` row for candidate C
    (never created one in this test), yet can still call the pre-existing
    candidate-scoped `POST /api/recruiter-actions/suggest` endpoint on C's
    behalf (`recruiter_actions/router.py`'s own docstring: "any recruiter can
    act on any candidate"). If this ever starts 403'ing/404'ing because of the
    assignment table, that is the release-blocking regression this test
    guards against.
    """
    match = await _make_job_match(db, candidate)

    # Confirm, directly against the table, that the (recruiter_a, candidate)
    # pair truly has zero assignment rows before making the call -- not an
    # assumption, an assertion.
    result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_a.id,
            RecruiterCandidateAssignment.candidate_user_id == candidate.id,
        )
    )
    assert result.scalar_one_or_none() is None
    assigned_recruiters = await assignment_repository.list_assigned_recruiters_for_candidate(
        db, candidate.id
    )
    assert assigned_recruiters == []

    response = client.post(
        "/api/recruiter-actions/suggest",
        headers=_auth_headers(str(recruiter_a.id)),
        json={"candidate_user_id": str(candidate.id), "job_match_id": str(match.id)},
    )

    data = assert_success(response)
    assert data["candidate_user_id"] == str(candidate.id)
    assert data["recruiter_user_id"] == str(recruiter_a.id)
    assert data["status"] == "pending"


# ---------------------------------------------------------------------------
# 2. POST /api/recruiter-assignments -- gated by
# require_permission("recruiter_assignments", "write").
# ---------------------------------------------------------------------------


async def test_assign_candidate_without_permission_returns_403(
    client: TestClient, recruiter_a: User, candidate: User
) -> None:
    response = client.post(
        "/api/recruiter-assignments",
        headers=_auth_headers(str(recruiter_a.id)),
        json={"candidate_user_id": str(candidate.id), "recruiter_user_id": str(recruiter_a.id)},
    )
    assert_error(response, 403)


async def test_assign_candidate_superuser_bypasses_gate_and_creates_row(
    client: TestClient, db: AsyncSession, superuser: User, recruiter_a: User, candidate: User
) -> None:
    """`is_superuser` short-circuits `user_has_permission` (Decision 1) without
    touching the role/permission-table lookup -- exercises the real
    `require_permission("recruiter_assignments", "write")` dependency on the
    router."""
    response = client.post(
        "/api/recruiter-assignments",
        headers=_auth_headers(str(superuser.id)),
        json={"candidate_user_id": str(candidate.id), "recruiter_user_id": str(recruiter_a.id)},
    )
    data = assert_success(response, status=201)
    assert data["candidate_user_id"] == str(candidate.id)
    assert data["recruiter_user_id"] == str(recruiter_a.id)

    rows = await assignment_repository.list_assignments_for_recruiter(db, recruiter_a.id)
    assert {row.candidate_user_id for row in rows} == {candidate.id}


async def test_assign_candidate_via_team_owner_role_permission_grant(
    client: TestClient, db: AsyncSession, recruiter_a: User, candidate: User
) -> None:
    """The *actual* production path: a user with the seeded `team_owner` role
    (granted `recruiter_assignments:write` by migration
    056_recruiter_assignments_permission.py) can create an assignment through
    the real role -> permission lookup, not a superuser bypass."""
    from app.modules.admin.models import Role

    result = await db.execute(select(Role).where(Role.name == "team_owner"))
    team_owner_role = result.scalar_one()
    actor = await _make_user(db, role_id=team_owner_role.id)

    response = client.post(
        "/api/recruiter-assignments",
        headers=_auth_headers(str(actor.id)),
        json={"candidate_user_id": str(candidate.id), "recruiter_user_id": str(recruiter_a.id)},
    )
    role_grant_data = assert_success(response, status=201)
    assert role_grant_data["candidate_user_id"] == str(candidate.id)
    assert role_grant_data["recruiter_user_id"] == str(recruiter_a.id)


# ---------------------------------------------------------------------------
# 3. Idempotency: assigning the same (recruiter, candidate) pair twice
# returns the same row, not a duplicate or an error.
# ---------------------------------------------------------------------------


async def test_assign_candidate_twice_is_idempotent_via_router(
    client: TestClient, db: AsyncSession, superuser: User, recruiter_a: User, candidate: User
) -> None:
    body = {"candidate_user_id": str(candidate.id), "recruiter_user_id": str(recruiter_a.id)}
    headers = _auth_headers(str(superuser.id))

    first = client.post("/api/recruiter-assignments", headers=headers, json=body)
    first_data = assert_success(first, status=201)

    second = client.post("/api/recruiter-assignments", headers=headers, json=body)
    second_data = assert_success(second, status=201)

    assert first_data["id"] == second_data["id"]

    result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_a.id,
            RecruiterCandidateAssignment.candidate_user_id == candidate.id,
        )
    )
    rows = result.scalars().all()
    assert len(rows) == 1


async def test_create_assignment_repository_is_idempotent_by_pair(
    db: AsyncSession, recruiter_a: User, candidate: User
) -> None:
    """Unit-level check directly on `repository.create_assignment`, bypassing
    the router entirely, per its own docstring's documented contract."""
    first = await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_a.id, candidate_user_id=candidate.id
    )
    await db.commit()

    second = await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_a.id, candidate_user_id=candidate.id
    )
    await db.commit()

    assert first.id == second.id

    result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_a.id,
            RecruiterCandidateAssignment.candidate_user_id == candidate.id,
        )
    )
    assert len(result.scalars().all()) == 1


# ---------------------------------------------------------------------------
# 4. DELETE /api/recruiter-assignments/{candidate_user_id} -- always scoped
# to the authenticated caller as recruiter_user_id; never another recruiter's
# row.
# ---------------------------------------------------------------------------


async def test_unassign_own_assignment_succeeds(
    client: TestClient,
    db: AsyncSession,
    recruiter_a: User,
    candidate: User,
) -> None:
    await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_a.id, candidate_user_id=candidate.id
    )
    await db.commit()

    response = client.delete(
        f"/api/recruiter-assignments/{candidate.id}",
        headers=_auth_headers(str(recruiter_a.id)),
    )
    assert response.status_code == 204

    result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_a.id,
            RecruiterCandidateAssignment.candidate_user_id == candidate.id,
        )
    )
    assert result.scalar_one_or_none() is None


async def test_unassign_does_not_delete_a_different_recruiters_row_for_same_candidate(
    client: TestClient,
    db: AsyncSession,
    recruiter_a: User,
    recruiter_b: User,
    candidate: User,
) -> None:
    """Recruiter A and Recruiter B are both assigned to the same candidate.
    Recruiter A calling DELETE on that candidate must remove only A's own
    row -- B's row survives untouched. The endpoint takes no
    `recruiter_user_id` request body/query param at all (it hardcodes the
    caller's own id at the router layer), so there is no field to try to
    impersonate B with; this test confirms the *effect* of that hardcoding:
    A's call can never reach B's row."""
    await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_a.id, candidate_user_id=candidate.id
    )
    await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_b.id, candidate_user_id=candidate.id
    )
    await db.commit()

    response = client.delete(
        f"/api/recruiter-assignments/{candidate.id}",
        headers=_auth_headers(str(recruiter_a.id)),
    )
    assert response.status_code == 204

    a_result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_a.id,
            RecruiterCandidateAssignment.candidate_user_id == candidate.id,
        )
    )
    assert a_result.scalar_one_or_none() is None

    b_result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_b.id,
            RecruiterCandidateAssignment.candidate_user_id == candidate.id,
        )
    )
    assert b_result.scalar_one_or_none() is not None


async def test_unassign_ignores_extra_recruiter_user_id_in_request_body(
    client: TestClient,
    db: AsyncSession,
    recruiter_a: User,
    recruiter_b: User,
    candidate: User,
) -> None:
    """Even if a caller tries to smuggle a different `recruiter_user_id` into
    the DELETE request body (the route signature declares no body parameter,
    so FastAPI ignores unrecognized JSON entirely), the endpoint must still
    resolve to the authenticated caller's own id, never B's."""
    await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_a.id, candidate_user_id=candidate.id
    )
    await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_b.id, candidate_user_id=candidate.id
    )
    await db.commit()

    response = client.request(
        "DELETE",
        f"/api/recruiter-assignments/{candidate.id}",
        headers=_auth_headers(str(recruiter_a.id)),
        json={"recruiter_user_id": str(recruiter_b.id)},
    )
    assert response.status_code == 204

    a_result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_a.id,
            RecruiterCandidateAssignment.candidate_user_id == candidate.id,
        )
    )
    assert a_result.scalar_one_or_none() is None

    b_result = await db.execute(
        select(RecruiterCandidateAssignment).where(
            RecruiterCandidateAssignment.recruiter_user_id == recruiter_b.id,
            RecruiterCandidateAssignment.candidate_user_id == candidate.id,
        )
    )
    assert b_result.scalar_one_or_none() is not None


async def test_unassign_nonexistent_pair_is_a_noop_not_an_error(
    client: TestClient, recruiter_a: User, candidate: User
) -> None:
    """No assignment row exists for this pair -- per repository.delete_assignment's
    documented idempotent-unassign contract, this must not error."""
    response = client.delete(
        f"/api/recruiter-assignments/{candidate.id}",
        headers=_auth_headers(str(recruiter_a.id)),
    )
    assert response.status_code == 204


# ---------------------------------------------------------------------------
# 5. GET /api/recruiter-assignments/my-candidates -- scoped to the
# authenticated recruiter only.
# ---------------------------------------------------------------------------


async def test_my_candidates_returns_only_callers_own_assignments(
    client: TestClient,
    db: AsyncSession,
    recruiter_a: User,
    recruiter_b: User,
) -> None:
    candidate_x = await _make_user(db)
    candidate_y = await _make_user(db)
    candidate_z = await _make_user(db)

    await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_a.id, candidate_user_id=candidate_x.id
    )
    await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_a.id, candidate_user_id=candidate_y.id
    )
    await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_b.id, candidate_user_id=candidate_z.id
    )
    await db.commit()

    response = client.get(
        "/api/recruiter-assignments/my-candidates",
        headers=_auth_headers(str(recruiter_a.id)),
    )
    data = assert_success(response)
    returned_candidate_ids = {a["candidate_user_id"] for a in data["assignments"]}
    assert returned_candidate_ids == {str(candidate_x.id), str(candidate_y.id)}
    assert str(candidate_z.id) not in returned_candidate_ids
    for assignment in data["assignments"]:
        assert assignment["recruiter_user_id"] == str(recruiter_a.id)


async def test_my_candidates_empty_for_recruiter_with_no_assignments(
    client: TestClient, recruiter_a: User
) -> None:
    response = client.get(
        "/api/recruiter-assignments/my-candidates",
        headers=_auth_headers(str(recruiter_a.id)),
    )
    data = assert_success(response)
    assert data["assignments"] == []


async def test_my_candidates_never_leaks_across_two_recruiters_symmetrically(
    client: TestClient,
    db: AsyncSession,
    recruiter_a: User,
    recruiter_b: User,
    candidate: User,
) -> None:
    """Both recruiters are assigned to the SAME candidate -- confirms scoping
    is by recruiter_user_id, not by candidate, and neither recruiter's list
    exposes the other's identity."""
    await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_a.id, candidate_user_id=candidate.id
    )
    await assignment_repository.create_assignment(
        db, recruiter_user_id=recruiter_b.id, candidate_user_id=candidate.id
    )
    await db.commit()

    response_a = client.get(
        "/api/recruiter-assignments/my-candidates",
        headers=_auth_headers(str(recruiter_a.id)),
    )
    data_a = assert_success(response_a)
    assert len(data_a["assignments"]) == 1
    assert data_a["assignments"][0]["recruiter_user_id"] == str(recruiter_a.id)

    response_b = client.get(
        "/api/recruiter-assignments/my-candidates",
        headers=_auth_headers(str(recruiter_b.id)),
    )
    data_b = assert_success(response_b)
    assert len(data_b["assignments"]) == 1
    assert data_b["assignments"][0]["recruiter_user_id"] == str(recruiter_b.id)
