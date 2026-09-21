"""Symmetric sealing for short secrets at rest (MFA, etc.).

Uses Fernet with a key derived from ``SECRET_KEY`` so no extra env var is required.
Legacy plaintext values remain readable via ``open_secret`` fallback.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    digest = hashlib.sha256(get_settings().SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal_secret(plaintext: str) -> str:
    """Encrypt a short secret for DB storage (returns url-safe text)."""
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def open_secret(stored: str) -> str:
    """Decrypt a sealed secret, or return ``stored`` unchanged if it is legacy plaintext."""
    if not stored:
        return stored
    try:
        return _fernet().decrypt(stored.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return stored


def open_secret_strict(stored: str) -> str:
    """Decrypt Fernet ciphertext, raising ``InvalidToken`` on every invalid input."""
    if not isinstance(stored, str) or not stored:
        raise InvalidToken
    try:
        return _fernet().decrypt(stored.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeEncodeError, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise InvalidToken from exc
