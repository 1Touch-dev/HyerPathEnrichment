"""JWT encode/decode helpers (PyJWT, HS256 only)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
from jwt import PyJWTError

# Hardcoded — do not honor env overrides that could enable weak algs.
JWT_ALGORITHM = "HS256"

LOGIN_MFA_PURPOSE = "login_mfa"

__all__ = [
    "JWT_ALGORITHM",
    "LOGIN_MFA_PURPOSE",
    "PyJWTError",
    "create_login_mfa_token",
    "create_user_access_token",
    "decode_access_token",
    "encode_access_token",
    "login_mfa_subject",
]


def encode_access_token(payload: dict[str, Any], secret_key: str) -> str:
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    payload = jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
    if not isinstance(payload, dict):
        raise PyJWTError("JWT payload must be an object")
    return payload


def create_user_access_token(
    user_id: str,
    email: str,
    *,
    secret_key: str,
    expires_minutes: int,
) -> tuple[str, str]:
    """Create a normal user access token shared by auth and impersonation restoration."""
    now = datetime.now(UTC)
    jti = f"{user_id}:{uuid4().hex}"
    payload = {
        "sub": user_id,
        "email": email,
        "jti": jti,
        "exp": now + timedelta(minutes=expires_minutes),
        "iat": now,
    }
    return encode_access_token(payload, secret_key), jti


def create_login_mfa_token(user_id: str, *, secret_key: str, expires_minutes: int) -> str:
    """Short-lived proof that the password (or Google identity) step succeeded.

    This is not an access token: it has no ``jti`` and carries ``purpose``.
    Session cookies are issued only after ``login_mfa_subject`` plus a valid TOTP.
    """
    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "purpose": LOGIN_MFA_PURPOSE,
        "exp": now + timedelta(minutes=expires_minutes),
        "iat": now,
    }
    return encode_access_token(payload, secret_key)


def login_mfa_subject(token: str, secret_key: str) -> str:
    """Return the user id bound to a login MFA challenge, or raise ``PyJWTError``."""
    payload = decode_access_token(token, secret_key)
    subject = payload.get("sub")
    if payload.get("purpose") != LOGIN_MFA_PURPOSE or not isinstance(subject, str) or not subject:
        raise PyJWTError("Invalid login MFA token")
    return subject
