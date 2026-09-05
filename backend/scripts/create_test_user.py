#!/usr/bin/env python3
"""Create (or reuse) a pre-verified user for Playwright integration tests.

Bypasses the real register -> email -> verify-email flow by writing a
verified `User` row directly, mirroring the pattern already used by the
backend's own pytest suite (see backend/tests/test_unverified_access.py).
Intended to be invoked by frontend/e2e/integration's auth setup, which then
logs in over HTTP to obtain real access_token/refresh_token cookies.

Prints a single JSON line ({"email": ..., "password": ...}) to stdout on
success; all diagnostic output goes to stderr.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


_PROD_LIKE_ENVS = frozenset({"production", "staging"})
_SUPERUSER_ALLOW_ENV = "ALLOW_E2E_SUPERUSER_BOOTSTRAP"


def validate_bootstrap_context(*, app_env: str, is_superuser: bool) -> None:
    normalized_env = app_env.strip().lower()
    if normalized_env in _PROD_LIKE_ENVS:
        raise RuntimeError("create_test_user.py is disabled when APP_ENV is staging or production")
    if is_superuser and os.getenv(_SUPERUSER_ALLOW_ENV, "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        raise RuntimeError(
            f"--is-superuser requires {_SUPERUSER_ALLOW_ENV}=1 so the non-production exception is explicit"
        )


async def _create_or_update_user(
    email: str, password: str, first_name: str, last_name: str, *, is_superuser: bool = False
) -> None:
    from sqlalchemy import select

    import app.database.orm_registry  # noqa: F401  (registers all ORM models/relationships)
    from app.auth.models import User
    from app.auth.password import hash_password
    from app.database.session import SessionLocal

    hashed = hash_password(password)

    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=email,
                hashed_password=hashed,
                first_name=first_name,
                last_name=last_name,
                is_verified=True,
                is_active=True,
                is_superuser=is_superuser,
            )
            session.add(user)
        else:
            user.hashed_password = hashed
            user.is_verified = True
            user.is_active = True
            user.deleted_at = None
            user.is_superuser = is_superuser

        await session.commit()


def main() -> int:
    from app.core.config import get_settings

    parser = argparse.ArgumentParser(
        description="Create a verified test user for e2e integration tests"
    )
    parser.add_argument("--email", default="e2e-integration@example.com")
    parser.add_argument("--password", default="IntegrationTest123")
    parser.add_argument("--first-name", default="E2E")
    parser.add_argument("--last-name", default="Integration")
    parser.add_argument(
        "--is-superuser",
        action="store_true",
        default=False,
        help="Create/update the user as a superuser (grants all admin RBAC permissions).",
    )
    args = parser.parse_args()
    validate_bootstrap_context(
        app_env=get_settings().app_env,
        is_superuser=args.is_superuser,
    )

    asyncio.run(
        _create_or_update_user(
            args.email,
            args.password,
            args.first_name,
            args.last_name,
            is_superuser=args.is_superuser,
        )
    )

    print(json.dumps({"email": args.email, "password": args.password}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
