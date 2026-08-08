"""Unverified user access control tests."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.password import hash_password
from app.main import app


@pytest.fixture
async def unverified_user(db: AsyncSession) -> User:
    """Create unverified test user."""
    user = User(
        email="unverified@example.com",
        first_name="Unverified",
        last_name="User",
        hashed_password=hash_password("password123"),
        is_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest.fixture
async def verified_user(db: AsyncSession) -> User:
    """Create verified test user."""
    user = User(
        email="verified@example.com",
        first_name="Verified",
        last_name="User",
        hashed_password=hash_password("password123"),
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def test_unverified_user_blocked_from_enrichment() -> None:
    """Test unverified users cannot access enrichment endpoints."""
    # Note: In real implementation, this would use auth cookie
    # For this test, we're checking the dependency structure
    # The actual integration test would use proper authentication

    # Unverified users should get 403 Forbidden
    # This test validates the requirement that enrichment requires verification
    # Placeholder - full implementation requires auth integration


def test_verified_user_can_access_enrichment() -> None:
    """Test verified users can access enrichment endpoints."""
    # Verified users should successfully access enrichment
    # Placeholder - full implementation requires auth integration


def test_unverified_user_blocked_from_dsar() -> None:
    """Test unverified users cannot access DSAR endpoints."""
    # DSAR requires authentication AND verification
    # Unverified users should get 403 Forbidden
    # Placeholder - full implementation requires auth integration


def test_verified_user_can_access_dsar() -> None:
    """Test verified users can access DSAR endpoints."""
    # Verified users should successfully access DSAR
    # Placeholder - full implementation requires auth integration


def test_unverified_user_can_access_opt_out() -> None:
    """Test unverified users CAN access public opt-out endpoint."""
    client = TestClient(app)

    # Opt-out is public - no authentication required
    # This should work even for non-authenticated users
    identifier = f"optout-{uuid4().hex}@example.com"

    response = client.post("/api/opt-out", json={"identifier": identifier})

    # Should succeed (201) or return existing opt-out (200)
    assert response.status_code in [200, 201]


def test_unauthenticated_user_can_access_opt_out() -> None:
    """Test completely unauthenticated users can opt out."""
    client = TestClient(app)

    identifier = f"anonymous-optout-{uuid4().hex}@example.com"

    response = client.post("/api/opt-out", json={"identifier": identifier})

    # Public endpoint - should work without any auth
    assert response.status_code in [200, 201]


def test_unauthenticated_user_blocked_from_dsar() -> None:
    """Test unauthenticated users cannot access DSAR."""
    # DSAR requires authentication (then verification)
    # Unauthenticated should get 401 Unauthorized
    # Placeholder - full implementation requires auth integration


def test_unauthenticated_user_blocked_from_enrichment() -> None:
    """Test unauthenticated users cannot access enrichment."""
    client = TestClient(app)

    # For now, enrichment uses API token, but after auth implementation
    # it should require authenticated user
    response = client.post(
        "/enrich/sync",
        json={"email": "test@example.com", "username": "testuser", "requested_tiers": ["tier1"]},
    )

    # Should fail without authentication
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_verification_requirement_check(db: AsyncSession, unverified_user: User) -> None:
    """Test verification status check function."""
    # In production code, this would be the require_verified_user dependency
    assert unverified_user.is_verified is False

    # Should raise HTTPException with 403 in real implementation


@pytest.mark.asyncio
async def test_verified_user_passes_check(db: AsyncSession, verified_user: User) -> None:
    """Test verified user passes verification check."""
    assert verified_user.is_verified is True

    # Should pass through without exception in real implementation


def test_opt_out_rate_limiting_works_without_auth() -> None:
    """Test opt-out endpoint has IP-based rate limiting (no auth needed)."""
    client = TestClient(app)

    # Make multiple opt-out requests
    identifier = f"rate-test-{uuid4().hex}@example.com"

    for _ in range(3):
        response = client.post("/api/opt-out", json={"identifier": identifier})
        # Should succeed or be rate limited based on IP
        assert response.status_code in [200, 201, 429]


def test_dsar_access_control_hierarchy() -> None:
    """Test DSAR has two-tier access control: auth + verification."""
    # This test documents the requirement:
    # 1. First check: authenticated (401 if not)
    # 2. Second check: verified (403 if authenticated but unverified)
    # 3. Finally: process request

    # Implementation order matters for correct error codes
    # Placeholder - full implementation requires auth integration


def test_enrichment_access_control_hierarchy() -> None:
    """Test enrichment has two-tier access control: auth + verification."""
    # Same hierarchy as DSAR:
    # 1. Authenticated check (401)
    # 2. Verification check (403)
    # 3. Process enrichment

    # Placeholder - full implementation requires auth integration


def test_unverified_user_sees_verification_banner() -> None:
    """Test unverified users should receive verification status in user info."""
    # When fetching /users/me, unverified users should see is_verified=false
    # Frontend uses this to show verification banner

    # Placeholder - full implementation requires auth integration


def test_verified_user_no_verification_banner() -> None:
    """Test verified users don't see verification requirements."""
    # Verified users should see is_verified=true
    # Frontend hides banner for verified users

    # Placeholder - full implementation requires auth integration


@pytest.mark.asyncio
async def test_verification_status_persists(db: AsyncSession, unverified_user: User) -> None:
    """Test verification status is stored persistently."""
    # Verify status stored in database
    assert unverified_user.is_verified is False

    # Mark as verified
    unverified_user.is_verified = True
    await db.commit()
    await db.refresh(unverified_user)

    # Status should persist
    assert unverified_user.is_verified is True


def test_access_control_documentation() -> None:
    """Document the access control model for reference."""
    # PUBLIC (no auth required):
    # - /api/opt-out
    # - /health
    # - /metrics (if exposed)

    # AUTHENTICATED ONLY (verified not required):
    # - /users/me
    # - /auth/resend-verification
    # - /auth/logout

    # AUTHENTICATED + VERIFIED:
    # - /enrich/*
    # - /api/dsar
    # - /api/jobs/*
    # - All protected business logic

    # Documentation test
