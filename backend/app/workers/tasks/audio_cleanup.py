"""Background worker task for audio cleanup and GDPR compliance.

Automatically deletes expired audio recordings from storage and database
to comply with data retention policies.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.database.session import SyncSessionLocal

logger = logging.getLogger(__name__)


class AudioStorageClient:
    """Interface for audio storage operations.

    Wraps R2StorageClient for audio file management.
    """

    def __init__(self) -> None:
        from app.storage.r2 import R2StorageClient

        self._storage = R2StorageClient()

    async def delete_audio(self, storage_path: str) -> bool:
        """Delete an audio file from storage.

        Args:
            storage_path: Storage path/key for the audio file

        Returns:
            True if deleted, False if not found or failed
        """
        try:
            return await self._storage.delete_object(storage_path)
        except Exception as exc:
            logger.warning(
                "Failed to delete audio file",
                exc_info=True,
                extra={"storage_path": storage_path[:64], "error": str(exc)},
            )
            return False


async def _cleanup_expired_audio_async(db: Session) -> dict[str, int]:
    """Internal async logic for audio cleanup.

    Args:
        db: Sync database session

    Returns:
        Dict with deleted_count and failed_count
    """
    # Import here to avoid circular dependencies at module load
    from sqlalchemy import text

    # Query expired recordings (limit batch size for memory)
    batch_limit = 1000
    now = datetime.utcnow()

    # Get expired recordings
    query = text("""
        SELECT id, storage_path, user_id
        FROM practice_audio_recordings
        WHERE expires_at < :now
        LIMIT :limit
    """)

    result = db.execute(query, params={"now": now, "limit": batch_limit})
    expired_recordings = result.fetchall()

    if not expired_recordings:
        logger.info("No expired audio recordings to clean up")
        return {"deleted_count": 0, "failed_count": 0}

    logger.info(
        f"Found {len(expired_recordings)} expired audio recordings to clean up",
        extra={"count": len(expired_recordings), "batch_limit": batch_limit},
    )

    # Delete from storage first, then from DB
    storage_client = AudioStorageClient()
    deleted_count = 0
    failed_count = 0
    successfully_deleted_ids: list[UUID] = []

    for record in expired_recordings:
        recording_id = record.id if hasattr(record, "id") else record[0]
        storage_path = record.storage_path if hasattr(record, "storage_path") else record[1]
        user_id = record.user_id if hasattr(record, "user_id") else record[2]

        try:
            # Attempt to delete from storage
            storage_deleted = await storage_client.delete_audio(storage_path)

            if storage_deleted:
                successfully_deleted_ids.append(recording_id)
                deleted_count += 1

                # Audit log for GDPR compliance
                logger.info(
                    "Audio recording deleted for GDPR compliance",
                    extra={
                        "recording_id": str(recording_id),
                        "user_id": str(user_id)[:8],
                        "storage_path": storage_path[:64],
                        "deleted_at": datetime.utcnow().isoformat(),
                        "reason": "expired_retention_period",
                    },
                )
            else:
                # Storage deletion failed, but we still want to remove DB record
                # to avoid orphaned records
                successfully_deleted_ids.append(recording_id)
                logger.warning(
                    "Storage deletion failed, removing DB record anyway",
                    extra={
                        "recording_id": str(recording_id),
                        "storage_path": storage_path[:64],
                    },
                )

        except Exception as exc:
            failed_count += 1
            logger.error(
                "Failed to delete audio recording",
                exc_info=True,
                extra={
                    "recording_id": str(recording_id),
                    "storage_path": storage_path[:64],
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

    # Delete successfully processed records from database
    if successfully_deleted_ids:
        try:
            delete_stmt = text("""
                DELETE FROM practice_audio_recordings
                WHERE id = ANY(:ids)
            """)
            db.execute(
                delete_stmt,
                params={"ids": [str(id) for id in successfully_deleted_ids]},
            )
            db.commit()

            logger.info(
                "Deleted audio records from database",
                extra={"count": len(successfully_deleted_ids)},
            )
        except Exception as exc:
            db.rollback()
            logger.error(
                "Failed to delete audio records from database",
                exc_info=True,
                extra={
                    "count": len(successfully_deleted_ids),
                    "error": str(exc),
                },
            )
            # Mark these as failed since DB deletion failed
            failed_count += len(successfully_deleted_ids)
            deleted_count -= len(successfully_deleted_ids)

    return {"deleted_count": deleted_count, "failed_count": failed_count}


def cleanup_expired_audio() -> dict[str, int]:
    """Clean up expired audio recordings for GDPR compliance.

    This is the main worker task scheduled as a cron job.
    Deletes audio files from storage and database after their retention period expires.

    Returns:
        Dict with deleted_count and failed_count

    Note:
        Runs daily at 2 AM UTC. Processes up to 1000 recordings per run.
        Audit logs are generated for each deletion for compliance tracking.
    """
    logger.info("Starting audio cleanup job")

    db: Session | None = None
    try:
        db = SyncSessionLocal()

        # Run async cleanup logic
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            stats = loop.run_until_complete(_cleanup_expired_audio_async(db))
        finally:
            loop.close()

        logger.info(
            "Audio cleanup job completed",
            extra={
                "deleted_count": stats["deleted_count"],
                "failed_count": stats["failed_count"],
            },
        )

        return stats

    except Exception as e:
        logger.error(
            "Audio cleanup job failed",
            extra={
                "error": str(e),
                "error_type": type(e).__name__,
            },
            exc_info=True,
        )

        # Return zero stats on failure
        return {"deleted_count": 0, "failed_count": 0}

    finally:
        if db:
            db.close()
