"""Business logic for ephemeral, on-demand resume tailoring (machine-2 track 10).

Mirrors `OutreachService.request_draft`'s enqueue-and-poll shape
(`backend/app/modules/outreach/service.py`), but this feature never writes a
database row for its result — RQ's own job-result store (bounded by
`result_ttl`) is the only place the tailored output ever lives. See
task-orchestration/machine-2-parallel-tracks/10-resume-tailoring.md for the
full "why ephemeral" rationale. Independent of `app.modules.outreach` — no
import from/into that module, this module only shares its calling convention.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.documents.models import CandidateDocument
from app.modules.resume_tailoring.schemas import (
    TailoredResumeResultResponse,
    TailorResumeJobResponse,
    TailorResumeRequest,
)
from app.workers.queue import QUEUE_OUTREACH

RESUME_TAILORING_RESULT_TTL_SECONDS = 1800

# Reuses the already-registered, already-worker-listened-to "outreach_generation"
# queue rather than inventing a new queue name: this track's own Design section
# says no edit is needed to app/workers/queue.py, and a brand-new queue name
# would also need registering in app/workers/rq_worker.py's queue list (out of
# scope here) before any worker process would ever pick up a job from it. This
# is queue-name reuse only — no import from/into app.modules.outreach itself.


async def request_tailoring(
    db: AsyncSession, *, user_id: UUID, body: TailorResumeRequest, redis_conn: Redis
) -> TailorResumeJobResponse:
    """Verify the candidate owns a completed document, then enqueue
    `tailor_resume_job` with an explicit `result_ttl`. No lock/dedup key is
    needed here the way `OutreachService.request_draft` uses one —
    regenerating the same tailoring twice is not "duplicate work" worth
    blocking; this feature is explicitly idempotent-safe to call repeatedly.
    """
    doc_result = await db.execute(
        select(CandidateDocument).where(
            CandidateDocument.id == UUID(body.document_id), CandidateDocument.user_id == user_id
        )
    )
    document = doc_result.scalar_one_or_none()
    if not document or document.processing_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A processed CV is required"
        )

    queue = Queue(QUEUE_OUTREACH, connection=redis_conn)
    rq_job = queue.enqueue(
        "app.workers.tasks.resume_tailoring.tailor_resume_job",
        str(user_id),
        body.document_id,
        body.target_company,
        body.target_role,
        job_timeout=60,
        result_ttl=RESUME_TAILORING_RESULT_TTL_SECONDS,
    )
    return TailorResumeJobResponse(rq_job_id=rq_job.id)


def get_tailoring_result(rq_job_id: str, redis_conn: Redis) -> TailoredResumeResultResponse:
    """`Queue.fetch_job(rq_job_id)` — same accessor
    `app/modules/admin/queues_service.py` already uses for introspecting job
    state. Maps RQ's `get_status()` plus, when finished, `job.result` (the
    dict `_tailor_resume_job` returned) into the response schema. Returns
    `status="not_found"` if `fetch_job` returns `None` (job expired past its
    `result_ttl`, or the id never existed) rather than 404ing.
    """
    queue = Queue(QUEUE_OUTREACH, connection=redis_conn)
    job = queue.fetch_job(rq_job_id)
    if job is None:
        return TailoredResumeResultResponse(status="not_found")

    rq_status = job.get_status()
    if rq_status != "finished":
        return TailoredResumeResultResponse(status=rq_status)

    result = job.result or {}
    return TailoredResumeResultResponse(
        status="finished",
        summary=result.get("summary"),
        emphasized_skills=result.get("emphasized_skills", []),
        reordered_bullets=result.get("reordered_bullets", []),
        research_degraded=result.get("research_degraded"),
    )
