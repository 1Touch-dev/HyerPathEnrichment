"""TOTP enroll/verify/disable — the verify_mfa() seam per Decision 5
(phase2_admin_module.md §9.10)."""

from __future__ import annotations

import pyotp
import pytest

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` — this file mixes
# sync and async test functions; asyncio_mode = "auto" (pyproject.toml)
# already runs async def tests without the marker, and applying it to the
# whole module also (harmlessly, but noisily) tags the sync tests.


async def test_enroll_generates_valid_provisioning_uri(db_session, regular_user):
    from app.modules.admin.mfa import enroll_mfa

    result = await enroll_mfa(db_session, regular_user)
    assert result.provisioning_uri.startswith("otpauth://totp/")
    assert regular_user.mfa_enabled is False  # not enabled until confirmed


async def test_confirm_enrollment_with_valid_code_enables_mfa(db_session, regular_user):
    from app.modules.admin.mfa import confirm_enrollment, enroll_mfa

    enrolled = await enroll_mfa(db_session, regular_user)
    code = pyotp.TOTP(enrolled.secret).now()
    await confirm_enrollment(db_session, regular_user, code)
    assert regular_user.mfa_enabled is True
    assert regular_user.mfa_enrolled_at is not None


async def test_confirm_enrollment_with_invalid_code_rejected(db_session, regular_user):
    from fastapi import HTTPException

    from app.modules.admin.mfa import confirm_enrollment, enroll_mfa

    await enroll_mfa(db_session, regular_user)
    with pytest.raises(HTTPException):
        await confirm_enrollment(db_session, regular_user, "000000")
    assert regular_user.mfa_enabled is False


async def test_disable_mfa_clears_secret_and_flag(db_session, regular_user):
    from app.modules.admin.mfa import confirm_enrollment, disable_mfa, enroll_mfa

    enrolled = await enroll_mfa(db_session, regular_user)
    code = pyotp.TOTP(enrolled.secret).now()
    await confirm_enrollment(db_session, regular_user, code)
    assert regular_user.mfa_enabled is True

    await disable_mfa(db_session, regular_user)
    assert regular_user.mfa_enabled is False
    assert regular_user.mfa_secret is None
    assert regular_user.mfa_enrolled_at is None


def test_verify_mfa_code_seam_is_pure_and_reusable(regular_user):
    from app.modules.admin.mfa import verify_mfa_code

    regular_user.mfa_secret = None
    assert verify_mfa_code(regular_user, "123456") is False


def test_verify_mfa_code_accepts_valid_totp(regular_user):
    from app.modules.admin.mfa import verify_mfa_code

    secret = pyotp.random_base32()
    regular_user.mfa_secret = secret
    code = pyotp.TOTP(secret).now()
    assert verify_mfa_code(regular_user, code) is True


def test_verify_mfa_code_rejects_wrong_code(regular_user):
    from app.modules.admin.mfa import verify_mfa_code

    secret = pyotp.random_base32()
    regular_user.mfa_secret = secret
    wrong_code = pyotp.TOTP(pyotp.random_base32()).now()
    # Astronomically unlikely to collide, but guard against the 1-in-a-million flake.
    if wrong_code == pyotp.TOTP(secret).now():
        wrong_code = "000000" if wrong_code != "000000" else "111111"
    assert verify_mfa_code(regular_user, wrong_code) is False
