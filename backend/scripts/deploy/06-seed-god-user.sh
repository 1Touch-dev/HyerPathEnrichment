#!/usr/bin/env bash
# 06-seed-god-user.sh — idempotent god superuser (works under APP_ENV=production|staging).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_common.sh
source "$SCRIPT_DIR/_common.sh"

GOD_EMAIL="${GOD_EMAIL:-god@hyrepath.dev}"
GOD_PASSWORD="${GOD_PASSWORD:-HyrepathGodTest123!}"

cid="$(compose ps -q api | head -n1)"
if [[ -z "$cid" ]]; then
  echo "ERROR: api container not running" >&2
  exit 1
fi

docker exec -w /app/backend -e GOD_EMAIL="$GOD_EMAIL" -e GOD_PASSWORD="$GOD_PASSWORD" -i "$cid" python - <<'PY'
import asyncio
import os
from sqlalchemy import select
import app.database.orm_registry  # noqa: F401
from app.auth.models import User
from app.auth.password import hash_password
from app.database.session import SessionLocal

EMAIL = os.environ["GOD_EMAIL"]
PASSWORD = os.environ["GOD_PASSWORD"]

async def main() -> None:
    async with SessionLocal() as session:
        result = await session.execute(select(User).where(User.email == EMAIL))
        user = result.scalar_one_or_none()
        hashed = hash_password(PASSWORD)
        if user is None:
            user = User(
                email=EMAIL,
                hashed_password=hashed,
                first_name="God",
                last_name="User",
                is_verified=True,
                is_active=True,
                is_superuser=True,
            )
            session.add(user)
            print(f"created {EMAIL}")
        else:
            user.hashed_password = hashed
            user.is_verified = True
            user.is_active = True
            user.is_superuser = True
            user.deleted_at = None
            print(f"updated {EMAIL}")
        await session.commit()

asyncio.run(main())
PY
