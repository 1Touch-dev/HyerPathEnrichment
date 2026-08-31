"""JWT encode/decode helpers (PyJWT, HS256 only)."""

from __future__ import annotations

from typing import Any

import jwt
from jwt import PyJWTError

# Hardcoded — do not honor env overrides that could enable weak algs.
JWT_ALGORITHM = "HS256"

__all__ = ["JWT_ALGORITHM", "PyJWTError", "decode_access_token", "encode_access_token"]


def encode_access_token(payload: dict[str, Any], secret_key: str) -> str:
    return jwt.encode(payload, secret_key, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    payload = jwt.decode(token, secret_key, algorithms=[JWT_ALGORITHM])
    if not isinstance(payload, dict):
        raise PyJWTError("JWT payload must be an object")
    return payload
