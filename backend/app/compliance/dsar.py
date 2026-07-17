"""DSAR (data subject access request) processing."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.audit import log_event
from app.compliance.identifiers import hash_identifier, linkedin_slug_from_identifier
from app.compliance.models import DsarRecord
from app.domain.enrichment import DsarRequest, DsarResponse
from app.domain.enums import AuditEventType, DsarStatus, DsarType
from app.modules.enrichment.models import JobRecord
from app.storage.models import PhotoCacheRecord
from app.storage.photo_cache import slug_hash
from app.enrichers.pipeline import Pipeline


async def process_dsar(db: AsyncSession, request: DsarRequest) -> DsarResponse:
    """Create and immediately process a DSAR (automated v1)."""
    identifier_hash = hash_identifier(request.identifier)
    record = DsarRecord(
        id=f"dsar_{uuid4().hex}",
        identifier_hash=identifier_hash,
        request_type=request.request_type.value,
        status=DsarStatus.pending.value,
        details={"notes": request.notes or ""},
    )
    db.add(record)
    await db.flush()

    await log_event(
        db,
        AuditEventType.dsar_created,
        identifier_hash,
        details={"dsar_id": record.id, "request_type": request.request_type.value},
    )

    if request.request_type == DsarType.deletion:
        summary = await _process_deletion(db, request.identifier, identifier_hash, record.id)
    else:
        summary = await build_access_summary(db, identifier_hash)

    now = datetime.now(timezone.utc)
    record.status = DsarStatus.completed.value
    record.completed_at = now
    record.details = {**(record.details or {}), "summary": summary}
    await db.flush()

    await log_event(
        db,
        AuditEventType.dsar_completed,
        identifier_hash,
        details={"dsar_id": record.id, "request_type": request.request_type.value, "summary": summary},
    )
    await db.commit()
    await db.refresh(record)

    return _to_response(record)


async def get_dsar(db: AsyncSession, dsar_id: str) -> DsarResponse | None:
    record = await db.get(DsarRecord, dsar_id)
    if record is None:
        return None
    return _to_response(record)


async def build_access_summary(db: AsyncSession, identifier_hash: str) -> dict[str, Any]:
    """Return counts and date ranges only — never dossier PII."""
    jobs = await _matching_jobs(db, identifier_hash)
    photo_cached = await _photo_cached_for_hash(db, identifier_hash)

    if not jobs:
        return {
            "job_count": 0,
            "photo_cached": photo_cached,
            "first_job_at": None,
            "last_job_at": None,
        }

    created_times = [job.created_at for job in jobs if job.created_at is not None]
    return {
        "job_count": len(jobs),
        "photo_cached": photo_cached,
        "first_job_at": min(created_times).isoformat() if created_times else None,
        "last_job_at": max(created_times).isoformat() if created_times else None,
    }


async def _process_deletion(
    db: AsyncSession,
    identifier: str,
    identifier_hash: str,
    dsar_id: str,
) -> dict[str, Any]:
    orchestrator = Pipeline(db)
    purge_result = await orchestrator.register_opt_out(identifier, reason=f"dsar_deletion:{dsar_id}")
    return {
        "suppressed": True,
        "jobs_cleared": purge_result.jobs_cleared,
        "photos_deleted": purge_result.photos_deleted,
        "r2_objects_deleted": purge_result.r2_objects_deleted,
    }


async def _matching_jobs(db: AsyncSession, identifier_hash: str) -> list[JobRecord]:
    from app.compliance.purge import _legacy_job_matches

    result = await db.execute(select(JobRecord))
    jobs = result.scalars().all()
    return [
        job
        for job in jobs
        if identifier_hash in (job.identifier_hashes or []) or _legacy_job_matches(job, identifier_hash)
    ]


async def _photo_cached_for_hash(db: AsyncSession, identifier_hash: str) -> bool:
    """Best-effort: check if any photo_cache row exists for jobs tied to this hash."""
    jobs = await _matching_jobs(db, identifier_hash)
    for job in jobs:
        payload = job.request_payload or {}
        linkedin_url = payload.get("linkedin_url")
        if not linkedin_url:
            continue
        slug = linkedin_slug_from_identifier(str(linkedin_url))
        if not slug:
            continue
        statement = select(PhotoCacheRecord).where(PhotoCacheRecord.slug_hash == slug_hash(slug))
        result = await db.execute(statement)
        if result.scalar_one_or_none() is not None:
            return True
    return False


def _to_response(record: DsarRecord) -> DsarResponse:
    details = record.details or {}
    summary = details.get("summary", {})
    return DsarResponse(
        id=record.id,
        status=DsarStatus(record.status),
        request_type=DsarType(record.request_type),
        created_at=record.created_at,
        completed_at=record.completed_at,
        summary=summary if isinstance(summary, dict) else {},
    )
