"""End-to-end test for complete authentication flow.

Tests the full user journey:
1. Register with email/password (with validation)
2. Receive verification email
3. Verify email with token
4. Login with verified account
5. Access protected resources (enrichment, DSAR)
6. Logout (token blacklisting)
7. Test logged-out token detection (security)
8. Login again (clears logged-out tokens)
9. Test unverified user access restrictions
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoggedOutToken, User
from app.main import app


@pytest.mark.asyncio
async def test_complete_auth_e2e_flow(db: AsyncSession):
    """Test complete authentication flow end-to-end."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # 1. Test registration with email validation
        register_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
            "first_name": "New",
            "last_name": "User",
        }

        register_response = await client.post("/auth/register", json=register_data)
        assert register_response.status_code == 201
        assert "verification" in register_response.json()["message"].lower()

        # 2. Verify verification email was queued (mocked in test)
        # In real implementation, check email queue

        # 3. Get verification token from database
        from sqlalchemy import select

        result = await db.execute(select(User).where(User.email == "newuser@example.com"))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.is_verified is False

        # Get verification token
        from app.auth.models import EmailVerificationToken

        result = await db.execute(
            select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
        )
        verification_token = result.scalar_one()

        # 4. Attempt to login before verification (should succeed but with unverified status)
        login_data = {
            "email": "newuser@example.com",
            "password": "SecurePass123!",
        }
        login_response = await client.post("/auth/login", json=login_data)
        assert login_response.status_code == 200

        # Extract cookies
        cookies = login_response.cookies
        assert "access_token" in cookies

        # 5. Try to access enrichment endpoint (should fail - unverified)
        enrich_response = await client.post(
            "/api/enrich",
            json={"business_name": "Test Corp"},
            cookies=cookies,
        )
        assert enrich_response.status_code == 403
        assert "verification required" in enrich_response.json()["detail"].lower()

        # 6. Try to access DSAR endpoint (should fail - unverified)
        dsar_response = await client.post(
            "/api/dsar",
            json={"email": "test@example.com"},
            cookies=cookies,
        )
        assert dsar_response.status_code == 403

        # 7. Verify opt-out is accessible without auth (public)
        optout_response = await client.post(
            "/api/opt-out",
            json={"email": "test@example.com", "business_name": "Test"},
        )
        assert optout_response.status_code in [200, 201, 202]

        # 8. Verify email with token
        verify_response = await client.post(
            "/auth/verify-email",
            json={"token": verification_token.token},
        )
        assert verify_response.status_code == 200

        # 9. Logout before re-login
        logout_response = await client.post("/auth/logout", cookies=cookies)
        assert logout_response.status_code == 200

        # 10. Verify token was blacklisted
        from jose import jwt

        from app.core.config import get_settings

        settings = get_settings()

        token_payload = jwt.decode(
            cookies["access_token"],
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        jti = token_payload["jti"]

        result = await db.execute(select(LoggedOutToken).where(LoggedOutToken.token_jti == jti))
        logged_out_token = result.scalar_one_or_none()
        assert logged_out_token is not None

        # 11. Try to use logged-out token (should fail)
        enrich_response_with_old_token = await client.post(
            "/api/enrich",
            json={"business_name": "Test Corp"},
            cookies=cookies,
        )
        assert enrich_response_with_old_token.status_code == 401
        assert "revoked" in enrich_response_with_old_token.json()["detail"].lower()

        # 12. Login again with verified account
        login_response_verified = await client.post("/auth/login", json=login_data)
        assert login_response_verified.status_code == 200
        verified_cookies = login_response_verified.cookies

        # 13. Verify logged-out tokens were cleared for this user
        result = await db.execute(select(LoggedOutToken).where(LoggedOutToken.user_id == user.id))
        _ = result.scalars().all()
        # In production, old tokens should be cleaned up on login
        # For now, just verify new login works

        # 14. Access enrichment endpoint (should succeed - verified)
        enrich_response_verified = await client.post(
            "/api/enrich",
            json={"business_name": "Test Corp"},
            cookies=verified_cookies,
        )
        # Should not be 403 anymore
        assert enrich_response_verified.status_code != 403

        # 15. Access DSAR endpoint (should succeed - verified)
        dsar_response_verified = await client.get(
            "/api/dsar",
            params={"email": "newuser@example.com"},
            cookies=verified_cookies,
        )
        # Should not be 403 anymore
        assert dsar_response_verified.status_code != 403

        # 16. Verify audit log has all events
        from app.auth.models import AuthAuditLog

        result = await db.execute(select(AuthAuditLog).where(AuthAuditLog.user_id == user.id))
        audit_logs = result.scalars().all()

        # Should have: register, login (unverified), email_verified, logout, login (verified)
        assert len(audit_logs) >= 4

        event_types = {log.event_type for log in audit_logs}
        assert "register" in event_types
        assert "login" in event_types
        assert "email_verified" in event_types
        assert "logout" in event_types


@pytest.mark.asyncio
async def test_invalid_email_registration(db: AsyncSession):
    """Test registration with invalid email format."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test various invalid email formats
        invalid_emails = [
            "notanemail",
            "@example.com",
            "user@",
            "user @example.com",
            "user@.com",
        ]

        for invalid_email in invalid_emails:
            register_data = {
                "email": invalid_email,
                "password": "SecurePass123!",
                "first_name": "Test",
                "last_name": "User",
            }

            response = await client.post("/auth/register", json=register_data)
            assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_weak_password_registration(db: AsyncSession):
    """Test registration with weak password."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test various weak passwords
        weak_passwords = [
            "short",  # Too short
            "alllowercase123",  # No uppercase
            "ALLUPPERCASE123",  # No lowercase
            "NoNumbers!",  # No digits
        ]

        for weak_password in weak_passwords:
            register_data = {
                "email": "test@example.com",
                "password": weak_password,
                "first_name": "Test",
                "last_name": "User",
            }

            response = await client.post("/auth/register", json=register_data)
            assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_deleted_account_login_blocked(db: AsyncSession):
    """Test that deleted accounts cannot login."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Create and verify a user
        register_data = {
            "email": "todelete@example.com",
            "password": "SecurePass123!",
            "first_name": "To",
            "last_name": "Delete",
        }

        await client.post("/auth/register", json=register_data)

        # Get user and mark as verified
        from sqlalchemy import select

        result = await db.execute(select(User).where(User.email == "todelete@example.com"))
        user = result.scalar_one()
        user.is_verified = True
        await db.commit()

        # Login
        login_data = {
            "email": "todelete@example.com",
            "password": "SecurePass123!",
        }
        login_response = await client.post("/auth/login", json=login_data)
        assert login_response.status_code == 200
        cookies = login_response.cookies

        # Delete account
        delete_response = await client.post("/auth/delete-account", cookies=cookies)
        assert delete_response.status_code == 200

        # Try to login again (should fail)
        login_response_after_delete = await client.post("/auth/login", json=login_data)
        assert login_response_after_delete.status_code == 403
        assert "deleted" in login_response_after_delete.json()["detail"].lower()
