"""Data-access layer for job_swipe. Reads Module 1's JobMatch/JobPosting tables directly (read-only)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings

# NOTE: JobMatch / JobPosting / JobPostingEmbedding come from Module 1 (phase2_module1.md
# §7.2) — imported here, never redefined. This import will fail with ModuleNotFoundError
# until Module 1 is implemented; see §4.1's explicit cross-module dependency note.
from app.modules.job_matching.models import JobMatch, JobPosting, JobPostingEmbedding
from app.modules.job_swipe.models import JobSwipeAction
from app.services.vector_search import _embedding_as_pgvector_literal, cosine_similarity

logger = logging.getLogger(__name__)

# Weight applied to the [0, 1] cosine-similarity boost before adding it to overall_score
# (which is on a much larger scale, e.g. 0-100). This only affects the in-memory ordering
# of get_unswiped_matches's returned page — never written back to JobMatch.overall_score.
_SIMILARITY_BOOST_WEIGHT = 15.0


async def _get_liked_posting_ids(db: AsyncSession, user_id: UUID) -> list[UUID]:
    """Job posting IDs the user previously swiped "right" or "up" on."""
    liked_match_ids_result = await db.execute(
        select(JobSwipeAction.job_match_id).where(
            JobSwipeAction.user_id == user_id,
            JobSwipeAction.direction.in_(["right", "up"]),
        )
    )
    liked_match_ids = [row[0] for row in liked_match_ids_result.all()]
    if not liked_match_ids:
        return []

    liked_posting_ids_result = await db.execute(
        select(JobMatch.job_posting_id).where(JobMatch.id.in_(liked_match_ids))
    )
    return [row[0] for row in liked_posting_ids_result.all()]


async def _compute_similarity_boosts(
    db: AsyncSession, candidate_posting_ids: list[UUID], liked_posting_ids: list[UUID]
) -> dict[UUID, float]:
    """Max cosine similarity of each candidate posting's embedding to any liked posting's embedding.

    Mirrors app.services.vector_search.similarity_search's dialect-aware approach: pgvector's
    ``<=>`` operator with bound CAST(:emb AS vector) params on PostgreSQL, a
    Python cosine_similarity() fallback on SQLite (or if the pgvector query fails).
    """
    if not candidate_posting_ids or not liked_posting_ids:
        return {}

    settings = get_settings()
    is_postgres = "postgresql" in settings.database_url.lower()

    if is_postgres:
        try:
            liked_embeddings_result = await db.execute(
                select(JobPostingEmbedding.embedding).where(
                    JobPostingEmbedding.job_posting_id.in_(liked_posting_ids)
                )
            )
            liked_vectors = [row[0] for row in liked_embeddings_result.all()]
            if not liked_vectors:
                return {}

            params: dict[str, Any] = {
                "candidate_ids": tuple(str(pid) for pid in candidate_posting_ids),
            }
            similarity_exprs: list[str] = []
            for i, vec in enumerate(liked_vectors):
                key = f"liked_emb_{i}"
                params[key] = _embedding_as_pgvector_literal(list(vec))
                similarity_exprs.append(f"(1 - (embedding <=> CAST(:{key} AS vector)))")
            best_expr = (
                f"GREATEST({', '.join(similarity_exprs)})"
                if len(similarity_exprs) > 1
                else similarity_exprs[0]
            )
            boost_sql = text(
                f"""
                SELECT job_posting_id, {best_expr} AS similarity
                FROM job_posting_embeddings
                WHERE job_posting_id IN :candidate_ids
                """
            ).bindparams(bindparam("candidate_ids", expanding=True))

            result = await db.execute(boost_sql, params)
            return {row.job_posting_id: float(row.similarity) for row in result.all()}
        except Exception as e:
            logger.error(
                "pgvector similarity boost failed, falling back to Python implementation",
                extra={"error": str(e)},
                exc_info=True,
            )
            # Fall through to Python implementation below.

    # SQLite fallback (and Postgres error fallback): compute cosine similarity in Python.
    candidate_embeddings_result = await db.execute(
        select(JobPostingEmbedding).where(
            JobPostingEmbedding.job_posting_id.in_(candidate_posting_ids)
        )
    )
    candidate_embeddings = candidate_embeddings_result.scalars().all()

    liked_embeddings_result = await db.execute(
        select(JobPostingEmbedding).where(JobPostingEmbedding.job_posting_id.in_(liked_posting_ids))
    )
    liked_embeddings = liked_embeddings_result.scalars().all()
    if not liked_embeddings:
        return {}

    boosts: dict[UUID, float] = {}
    for candidate in candidate_embeddings:
        boosts[candidate.job_posting_id] = max(
            cosine_similarity(candidate.embedding, liked.embedding) for liked in liked_embeddings
        )
    return boosts


async def get_unswiped_matches(
    db: AsyncSession, user_id: UUID, limit: int
) -> list[tuple[JobMatch, JobPosting]]:
    """Manual entries (Module F, §10.6/§10.7) are excluded via job_posting_id.is_not(None)
    rather than outer-joined with degraded fields: swiping is specifically for
    scanner-discovered matches the candidate hasn't reacted to yet, and a job the
    candidate typed in themselves (added straight to the tracker, application_status
    "new") has no "discovery" moment to swipe on — it should never appear in this deck.
    """
    already_swiped = select(JobSwipeAction.job_match_id).where(JobSwipeAction.user_id == user_id)
    result = await db.execute(
        select(JobMatch, JobPosting)
        .join(JobPosting, JobMatch.job_posting_id == JobPosting.id)
        .where(
            JobMatch.user_id == user_id,
            JobMatch.id.not_in(already_swiped),
            JobMatch.job_posting_id.is_not(None),
        )
        .order_by(JobMatch.overall_score.desc())
        .limit(limit)
    )
    rows = [(m, p) for m, p in result.all()]
    if not rows:
        return rows

    liked_posting_ids = await _get_liked_posting_ids(db, user_id)
    if not liked_posting_ids:
        return rows

    candidate_posting_ids = [p.id for _, p in rows]
    boosts = await _compute_similarity_boosts(db, candidate_posting_ids, liked_posting_ids)
    if not boosts:
        return rows

    def _final_score(row: tuple[JobMatch, JobPosting]) -> float:
        match, posting = row
        return match.overall_score + _SIMILARITY_BOOST_WEIGHT * boosts.get(posting.id, 0.0)

    rows.sort(key=_final_score, reverse=True)
    return rows


async def record_swipe(
    db: AsyncSession, job_match_id: UUID, user_id: UUID, direction: str
) -> JobSwipeAction:
    existing = await db.execute(
        select(JobSwipeAction).where(JobSwipeAction.job_match_id == job_match_id)
    )
    action = existing.scalar_one_or_none()
    if action:
        action.direction = direction
        action.created_at = datetime.now(UTC)
    else:
        from uuid import uuid4

        action = JobSwipeAction(
            id=uuid4(), job_match_id=job_match_id, user_id=user_id, direction=direction
        )
        db.add(action)
    await db.commit()
    await db.refresh(action)
    return action


async def get_last_swipe(db: AsyncSession, user_id: UUID) -> JobSwipeAction | None:
    """Most recent swipe action by this user, if any."""
    result = await db.execute(
        select(JobSwipeAction)
        .where(JobSwipeAction.user_id == user_id)
        .order_by(JobSwipeAction.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def delete_swipe(db: AsyncSession, swipe_id: UUID) -> None:
    """Delete a swipe action by id (no-op if it no longer exists)."""
    result = await db.execute(select(JobSwipeAction).where(JobSwipeAction.id == swipe_id))
    swipe = result.scalar_one_or_none()
    if swipe:
        await db.delete(swipe)
        await db.commit()
