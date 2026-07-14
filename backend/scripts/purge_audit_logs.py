#!/usr/bin/env python3
"""Delete audit log rows older than AUDIT_LOG_RETENTION_YEARS. Run via cron."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.config import get_settings
from app.models import AuditLog
from app.storage.db import SessionLocal, init_db


async def main() -> None:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.audit_log_retention_years * 365)

    await init_db()
    async with SessionLocal() as session:
        result = await session.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
        await session.commit()
        print(f"purged {result.rowcount} audit log rows older than {cutoff.isoformat()}")


if __name__ == "__main__":
    asyncio.run(main())
