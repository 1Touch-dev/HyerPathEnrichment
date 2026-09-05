"""Business logic for manual job entries (Module 4, Module F)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.manual_jobs import repository
from app.modules.manual_jobs.schemas import CreateManualJobEntryRequest, ManualJobEntryResponse
from app.observability.manual_jobs_metrics import manual_job_entries_created_total


async def create_manual_entry(
    db: AsyncSession, user_id: UUID, request: CreateManualJobEntryRequest
) -> ManualJobEntryResponse:
    entry, match = await repository.create_manual_entry(
        db,
        user_id,
        {
            "title": request.title,
            "company": request.company,
            "location": request.location,
            "source_label": request.source_label,
            "source_url": request.source_url,
            "notes": request.notes,
        },
    )

    manual_job_entries_created_total.inc()

    return ManualJobEntryResponse(
        id=str(entry.id),
        title=entry.title,
        company=entry.company,
        location=entry.location,
        source_label=entry.source_label,
        source_url=entry.source_url,
        notes=entry.notes,
        job_match_id=str(match.id),
        created_at=entry.created_at,
    )
