"""TOTP MFA: enroll/verify/disable for any user's own account. Enforcement is
NOT wired into the main login flow in this plan (Decision 5) — the one place
it IS enforced is impersonation start (§8.14), per docs/admin-module-research.md
§11.5's explicit requirement."""

from __future__ import annotations

import pyotp
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.core.config import get_settings
from app.core.secret_box import open_secret, seal_secret
from app.modules.admin.schemas import MfaEnrollResponse


def _raw_mfa_secret(user: User) -> str | None:
    if not user.mfa_secret:
        return None
    return open_secret(user.mfa_secret)


async def enroll_mfa(db: AsyncSession, user: User) -> MfaEnrollResponse:
    secret = pyotp.random_base32()
    # Store sealed; return plaintext once so the client can show the QR / backup.
    user.mfa_secret = seal_secret(secret)
    # mfa_enabled flips to True only after a successful verify_mfa_code call
    # (confirm_enrollment below) — never on enroll alone, so a user who
    # generates a QR code but never scans it isn't locked into an unusable state.
    await db.flush()
    await db.commit()

    settings = get_settings()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=user.email, issuer_name=settings.admin_mfa_issuer_name)
    return MfaEnrollResponse(secret=secret, provisioning_uri=uri)


def verify_mfa_code(user: User, code: str) -> bool:
    """The `verify_mfa()` seam per Decision 5 — a pure function, easy to unit
    test and easy to call from any future enforcement point without touching
    this module's internals."""
    raw = _raw_mfa_secret(user)
    if not raw:
        return False
    totp = pyotp.TOTP(raw)
    return bool(totp.verify(code, valid_window=1))


async def confirm_enrollment(db: AsyncSession, user: User, code: str) -> None:
    if not verify_mfa_code(user, code):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid MFA code")
    from datetime import UTC, datetime

    # Lazy-upgrade legacy plaintext secrets after a successful confirm.
    raw = _raw_mfa_secret(user)
    if raw and user.mfa_secret == raw:
        user.mfa_secret = seal_secret(raw)

    user.mfa_enabled = True
    user.mfa_enrolled_at = datetime.now(UTC)
    await db.flush()
    await db.commit()


async def disable_mfa(db: AsyncSession, user: User) -> None:
    user.mfa_enabled = False
    user.mfa_secret = None
    user.mfa_enrolled_at = None
    await db.flush()
    await db.commit()
