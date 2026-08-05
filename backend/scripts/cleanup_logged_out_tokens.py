#!/usr/bin/env python
"""
Cleanup expired logged-out tokens from PostgreSQL.

This script should be run periodically (e.g., daily via cron) to remove
expired tokens from the database. Redis entries expire automatically via TTL.

Usage:
    python backend/scripts/cleanup_logged_out_tokens.py

Cron example (daily at 2 AM):
    0 2 * * * cd /app && python backend/scripts/cleanup_logged_out_tokens.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from app.auth.logged_out_tokens import LoggedOutTokenService
from app.database.session import get_db_session
from app.infrastructure.redis import get_redis_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    """Run cleanup task."""
    logger.info("Starting logged-out tokens cleanup...")

    try:
        redis_client = get_redis_client()
        blacklist_service = LoggedOutTokenService(redis_client)

        async for db in get_db_session():
            deleted_count = await blacklist_service.cleanup_expired_logout_tokens(db)
            logger.info(f"Cleanup complete. Deleted {deleted_count} expired tokens.")
            break  # Only need one session

    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
