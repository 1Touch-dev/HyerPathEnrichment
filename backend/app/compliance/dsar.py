"""DSAR (data subject access request) processing."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.audit import log_event
from app.compliance.identifiers import hash_identifier, linkedin_slug_from_identifier
from app.compliance.models import DsarRecord
from app.domain.dossier import Dossier
from app.domain.enrichment import DsarRequest, DsarResponse
from app.domain.enums import AuditEventType, DsarStatus, DsarType
from app.enrichers.pipeline import Pipeline
from app.modules.enrichment.models import JobRecord
from app.storage.models import PhotoCacheRecord
from app.storage.photo_cache import slug_hash


async def process_dsar(db: AsyncSession, request: DsarRequest, user_id: UUID) -> DsarResponse:
    """
    Create and immediately process a DSAR (automated v1).

    Args:
        db: Database session
        request: DSAR request payload
        user_id: Authenticated user ID (for access control)

    Returns:
        DSAR response with summary
    """
    identifier_hash = hash_identifier(request.identifier)
    record = DsarRecord(
        id=f"dsar_{uuid4().hex}",
        user_id=user_id,
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
        details={
            "dsar_id": record.id,
            "request_type": request.request_type.value,
            "user_id": str(user_id),
        },
    )

    if request.request_type == DsarType.deletion:
        summary = await _process_deletion(db, request.identifier, identifier_hash, record.id)
    else:
        summary = await build_access_summary(db, identifier_hash, request.identifier)

    now = datetime.now(UTC)
    record.status = DsarStatus.completed.value
    record.completed_at = now
    record.details = {**(record.details or {}), "summary": summary}
    await db.flush()

    await log_event(
        db,
        AuditEventType.dsar_completed,
        identifier_hash,
        details={
            "dsar_id": record.id,
            "request_type": request.request_type.value,
            "user_id": str(user_id),
            "summary": summary,
        },
    )
    await db.commit()
    await db.refresh(record)

    return _to_response(record)


async def get_dsar(db: AsyncSession, dsar_id: str, user_id: UUID) -> DsarResponse | None:
    """
    Retrieve DSAR record by ID.

    Args:
        db: Database session
        dsar_id: DSAR record ID
        user_id: Authenticated user ID (for access control)

    Returns:
        DSAR response if found and user has access, None otherwise
    """
    result = await db.execute(
        select(DsarRecord).where(
            DsarRecord.id == dsar_id,
            DsarRecord.user_id == user_id,  # Ensure user can only access their own DSAR
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    return _to_response(record)


async def build_access_summary(
    db: AsyncSession, identifier_hash: str, original_identifier: str | None = None
) -> dict[str, Any]:
    """Return complete enriched data with full transparency for data access requests."""
    jobs = await _matching_jobs(db, identifier_hash)
    photo_cached = await _photo_cached_for_hash(db, identifier_hash)

    if not jobs:
        return {
            "job_count": 0,
            "photo_cached": photo_cached,
            "first_job_at": None,
            "last_job_at": None,
            "identifier_provided": original_identifier,
            "enriched_data": None,
        }

    created_times = [job.created_at for job in jobs if job.created_at is not None]
    merged_dossier = _merge_job_dossiers(jobs)

    return {
        "job_count": len(jobs),
        "photo_cached": photo_cached,
        "first_job_at": min(created_times).isoformat() if created_times else None,
        "last_job_at": max(created_times).isoformat() if created_times else None,
        "identifier_provided": original_identifier,
        "enriched_data": merged_dossier.model_dump(mode="json", exclude_none=True)
        if merged_dossier
        else None,
    }


async def _process_deletion(
    db: AsyncSession,
    identifier: str,
    identifier_hash: str,
    dsar_id: str,
) -> dict[str, Any]:
    orchestrator = Pipeline(db)
    purge_result = await orchestrator.register_opt_out(
        identifier, reason=f"dsar_deletion:{dsar_id}"
    )
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
        if identifier_hash in (job.identifier_hashes or [])
        or _legacy_job_matches(job, identifier_hash)
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


def _merge_job_dossiers(jobs: list[JobRecord]) -> Dossier | None:
    """Merge dossiers from multiple jobs into one comprehensive view."""
    if not jobs:
        return None

    merged = Dossier()
    handles_seen: set[tuple[str, str]] = set()
    emails_seen: set[str] = set()
    verified_emails_seen: set[str] = set()
    sources_seen: set[str] = set()

    for job in jobs:
        try:
            dossier = Dossier.model_validate(job.dossier_payload or {})
        except Exception:
            continue

        if dossier.photo and merged.photo is None:
            merged.photo = dossier.photo

        for handle in dossier.handles:
            key = (handle.platform.lower(), handle.username.lower())
            if key not in handles_seen:
                handles_seen.add(key)
                merged.handles.append(handle)
            else:
                for idx, existing in enumerate(merged.handles):
                    existing_key = (existing.platform.lower(), existing.username.lower())
                    if existing_key == key and handle.confidence > existing.confidence:
                        merged.handles[idx] = handle
                        break

        for email in dossier.emails:
            normalized = email.lower()
            if normalized not in emails_seen:
                emails_seen.add(normalized)
                merged.emails.append(email)

        for verified_email in dossier.verified_emails:
            normalized = verified_email.value.lower()
            if normalized not in verified_emails_seen:
                verified_emails_seen.add(normalized)
                merged.verified_emails.append(verified_email)

        if dossier.github:
            if not merged.github:
                merged.github = dossier.github
            else:
                merged.github.update(dossier.github)

        for coworker in dossier.coworkers:
            if coworker not in merged.coworkers:
                merged.coworkers.append(coworker)

        for job_listing in dossier.jobs:
            if job_listing not in merged.jobs:
                merged.jobs.append(job_listing)

        if dossier.business and merged.business is None:
            merged.business = dossier.business

        merged.confidence.extend(dossier.confidence)

        for source in dossier.sources:
            if source not in sources_seen:
                sources_seen.add(source)
                merged.sources.append(source)

        if dossier.metadata:
            if not merged.metadata:
                merged.metadata = {}
            merged.metadata.update(dossier.metadata)

    return merged if (merged.photo or merged.handles or merged.emails) else None
