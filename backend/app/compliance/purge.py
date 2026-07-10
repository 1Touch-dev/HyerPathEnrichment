"""Erase stored enrichment data for a suppressed identifier."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.identifiers import hash_identifier, linkedin_slug_from_identifier, request_identifier_values
from app.models import EnrichmentRequest, JobRecord, JobStatus, PhotoCacheRecord
from app.storage.photo_cache import PhotoCache, slug_hash
from app.storage.r2 import R2StorageClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PurgeResult:
    jobs_cleared: int = 0
    photos_deleted: int = 0
    r2_objects_deleted: int = 0


async def purge_identifier_data(db: AsyncSession, identifier: str) -> PurgeResult:
    """Clear dossiers, photo cache, and object storage for one identifier hash."""
    target_hash = hash_identifier(identifier)
    jobs_cleared = await _purge_matching_jobs(db, target_hash)
    photos_deleted, r2_objects_deleted = await _purge_photo_cache(db, identifier)
    return PurgeResult(
        jobs_cleared=jobs_cleared,
        photos_deleted=photos_deleted,
        r2_objects_deleted=r2_objects_deleted,
    )


async def _purge_matching_jobs(db: AsyncSession, target_hash: str) -> int:
    result = await db.execute(select(JobRecord))
    jobs = result.scalars().all()
    cleared = 0
    now = datetime.now(timezone.utc)

    for job in jobs:
        stored_hashes = list(job.identifier_hashes or [])
        if target_hash not in stored_hashes and not _legacy_job_matches(job, target_hash):
            continue

        job.dossier_payload = {}
        job.status = JobStatus.purged.value
        job.updated_at = now
        cleared += 1

    if cleared:
        await db.flush()
    return cleared


def _legacy_job_matches(job: JobRecord, target_hash: str) -> bool:
    """Fallback for jobs created before identifier_hashes was populated."""
    try:
        request = EnrichmentRequest.model_validate(job.request_payload)
    except Exception:
        return False

    return any(hash_identifier(value) == target_hash for value in request_identifier_values(request))


async def _purge_photo_cache(db: AsyncSession, identifier: str) -> tuple[int, int]:
    slug = linkedin_slug_from_identifier(identifier)
    if not slug:
        return 0, 0

    statement = select(PhotoCacheRecord).where(PhotoCacheRecord.slug_hash == slug_hash(slug))
    result = await db.execute(statement)
    record = result.scalar_one_or_none()
    if record is None:
        return 0, 0

    r2_deleted = 0
    if record.asset_key:
        storage = R2StorageClient()
        try:
            if await storage.delete_object(record.asset_key):
                r2_deleted = 1
        except Exception:
            logger.warning(
                "failed to delete R2 object for slug_hash=%s",
                record.slug_hash[:12],
                exc_info=True,
            )

    await db.delete(record)
    await db.flush()

    cache = PhotoCache()
    await cache.delete(slug)

    return 1, r2_deleted
