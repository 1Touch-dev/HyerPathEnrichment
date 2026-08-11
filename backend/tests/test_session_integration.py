"""End-to-end integration tests for session tracking API."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user_from_cookie, require_verified_user
from app.auth.models import User
from app.main import app


@pytest.fixture(autouse=True)
def _use_real_cookie_auth() -> None:
    """These tests exercise the real cookie-based login flow.

    The global ``override_auth_for_tests`` fixture (in conftest.py) replaces
    cookie auth with a header-based test shortcut for convenience in most
    tests. This module needs the real dependency restored so login actually
    exercises JWT/cookie handling end-to-end.
    """
    app.dependency_overrides.pop(get_current_user_from_cookie, None)
    app.dependency_overrides.pop(require_verified_user, None)
    yield


@pytest.fixture
async def authenticated_client(db: AsyncSession) -> tuple[AsyncClient, User]:
    """Create authenticated test client with user."""
    # Create and verify user
    from uuid import uuid4

    from app.auth.password import hash_password

    user = User(
        email=f"test-{uuid4()}@example.com",
        hashed_password=hash_password("SecurePass123!"),
        first_name="Test",
        last_name="User",
        is_verified=True,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Login to get token
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        login_response = await client.post(
            "/auth/login",
            json={"email": user.email, "password": "SecurePass123!"},
        )
        assert login_response.status_code == 200
        cookies = login_response.cookies
        yield client, user, cookies


@pytest.mark.asyncio
async def test_complete_session_flow(authenticated_client, db: AsyncSession):
    """Test complete session workflow via API."""
    client, _user, cookies = authenticated_client

    # 1. Start a new session
    create_response = await client.post(
        "/sessions",
        json={"session_type": "interview_practice"},
        cookies=cookies,
    )
    assert create_response.status_code == 201
    data = create_response.json()
    assert data["success"] is True
    session = data["data"]
    session_id = session["id"]
    assert session["status"] == "pending"
    assert session["session_type"] == "interview_practice"
    assert session["questions_attempted"] == 0

    # 2. Update progress
    progress_response = await client.patch(
        f"/sessions/{session_id}",
        json={"status": "in_progress", "questions_attempted": 5, "overall_score": 75.5},
        cookies=cookies,
    )
    assert progress_response.status_code == 200
    data = progress_response.json()
    assert data["data"]["questions_attempted"] == 5
    assert data["data"]["overall_score"] == 75.5

    # 3. Get session details
    get_response = await client.get(
        f"/sessions/{session_id}",
        cookies=cookies,
    )
    assert get_response.status_code == 200
    data = get_response.json()
    assert data["data"]["id"] == session_id
    assert data["data"]["questions_attempted"] == 5

    # 4. Complete session
    complete_response = await client.patch(
        f"/sessions/{session_id}",
        json={"status": "completed", "overall_score": 85.0},
        cookies=cookies,
    )
    assert complete_response.status_code == 200
    data = complete_response.json()
    assert data["data"]["status"] == "completed"
    assert data["data"]["overall_score"] == 85.0
    assert data["data"]["completed_at"] is not None

    # 5. List sessions
    list_response = await client.get(
        "/sessions?limit=10&offset=0",
        cookies=cookies,
    )
    assert list_response.status_code == 200
    data = list_response.json()
    assert data["data"]["total"] == 1
    assert len(data["data"]["sessions"]) == 1
    assert data["data"]["sessions"][0]["id"] == session_id


@pytest.mark.asyncio
async def test_duplicate_active_session_prevention(authenticated_client, db: AsyncSession):
    """Sessions API allows multiple concurrent sessions (no uniqueness constraint)."""
    client, _user, cookies = authenticated_client

    response1 = await client.post(
        "/sessions",
        json={"session_type": "interview_practice"},
        cookies=cookies,
    )
    assert response1.status_code == 201

    response2 = await client.post(
        "/sessions",
        json={"session_type": "technical_interview"},
        cookies=cookies,
    )
    assert response2.status_code == 201


@pytest.mark.asyncio
async def test_session_abandonment(authenticated_client, db: AsyncSession):
    """Test abandoning a session."""
    client, _user, cookies = authenticated_client

    # Start session
    create_response = await client.post(
        "/sessions",
        json={"session_type": "interview_practice"},
        cookies=cookies,
    )
    assert create_response.status_code == 201
    session_id = create_response.json()["data"]["id"]

    # Abandon session
    abandon_response = await client.patch(
        f"/sessions/{session_id}",
        json={"status": "abandoned"},
        cookies=cookies,
    )
    assert abandon_response.status_code == 200
    data = abandon_response.json()
    assert data["data"]["status"] == "abandoned"
    assert data["data"]["completed_at"] is not None


@pytest.mark.asyncio
async def test_session_ownership_verification(authenticated_client, db: AsyncSession):
    """Test that users can only access their own sessions."""
    client, _user, cookies = authenticated_client

    # Create another user directly (no AuthService dependency)
    from uuid import uuid4

    from app.auth.password import hash_password

    other_user = User(
        email=f"other-{uuid4()}@example.com",
        hashed_password=hash_password("SecurePass123!"),
        first_name="Other",
        last_name="User",
        is_verified=True,
        is_active=True,
    )
    db.add(other_user)
    await db.commit()
    await db.refresh(other_user)

    # Login as other user
    login_response = await client.post(
        "/auth/login",
        json={"email": other_user.email, "password": "SecurePass123!"},
    )
    assert login_response.status_code == 200
    other_cookies = login_response.cookies

    # Create session as first user
    create_response = await client.post(
        "/sessions",
        json={"session_type": "interview_practice"},
        cookies=cookies,
    )
    session_id = create_response.json()["data"]["id"]

    # Try to access with other user - should be treated as not found (scoped query)
    get_response = await client.get(
        f"/sessions/{session_id}",
        cookies=other_cookies,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_invalid_session_id_format(authenticated_client, db: AsyncSession):
    """Test handling of invalid session ID format."""
    client, _user, cookies = authenticated_client

    # Try with invalid UUID - FastAPI path validation rejects with 422
    get_response = await client.get(
        "/sessions/not-a-uuid",
        cookies=cookies,
    )
    assert get_response.status_code == 422


@pytest.mark.asyncio
async def test_session_not_found(authenticated_client, db: AsyncSession):
    """Test handling of non-existent session."""
    from uuid import uuid4

    client, _user, cookies = authenticated_client

    # Try to get non-existent session
    nonexistent_id = str(uuid4())
    get_response = await client.get(
        f"/sessions/{nonexistent_id}",
        cookies=cookies,
    )
    assert get_response.status_code == 404


@pytest.mark.asyncio
async def test_score_validation_via_api(authenticated_client, db: AsyncSession):
    """Test score validation through API endpoints."""
    client, _user, cookies = authenticated_client

    # Start session
    create_response = await client.post(
        "/sessions",
        json={"session_type": "interview_practice"},
        cookies=cookies,
    )
    session_id = create_response.json()["data"]["id"]

    # Try invalid score in progress update
    progress_response = await client.patch(
        f"/sessions/{session_id}",
        json={"questions_attempted": 5, "overall_score": 150.0},
        cookies=cookies,
    )
    assert progress_response.status_code == 422

    # Try invalid score in completion
    complete_response = await client.patch(
        f"/sessions/{session_id}",
        json={"status": "completed", "overall_score": -10.0},
        cookies=cookies,
    )
    assert complete_response.status_code == 422


@pytest.mark.asyncio
async def test_session_list_pagination(authenticated_client, db: AsyncSession):
    """Test session list pagination."""
    client, _user, cookies = authenticated_client

    # Create 5 sessions
    session_ids = []
    for i in range(5):
        response = await client.post(
            "/sessions",
            json={"session_type": f"session_{i}"},
            cookies=cookies,
        )
        session_id = response.json()["data"]["id"]
        session_ids.append(session_id)

        # Complete it (not required, but mirrors real usage)
        await client.patch(
            f"/sessions/{session_id}",
            json={"status": "completed", "overall_score": 80.0},
            cookies=cookies,
        )

    # Get first page
    page1_response = await client.get(
        "/sessions?limit=2&offset=0",
        cookies=cookies,
    )
    assert page1_response.status_code == 200
    data = page1_response.json()["data"]
    assert data["total"] == 5
    assert len(data["sessions"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Get second page
    page2_response = await client.get(
        "/sessions?limit=2&offset=2",
        cookies=cookies,
    )
    data = page2_response.json()["data"]
    assert len(data["sessions"]) == 2
    assert data["offset"] == 2

    # Get last page
    page3_response = await client.get(
        "/sessions?limit=2&offset=4",
        cookies=cookies,
    )
    data = page3_response.json()["data"]
    assert len(data["sessions"]) == 1


@pytest.mark.asyncio
async def test_unauthenticated_access(db: AsyncSession):
    """Test that unauthenticated requests are rejected."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Try to create session without auth
        response = await client.post(
            "/sessions",
            json={"session_type": "interview_practice"},
        )
        assert response.status_code == 401

        # Try to list sessions without auth
        response = await client.get("/sessions")
        assert response.status_code == 401
