"""Data-access layer for job matching. Workers import this, never service.py."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select, literal_column

from app.core.config import get_settings
from app.modules.job_matching.models import (
    CandidateJobPreferences,
    JobMatch,
    JobPosting,
    JobPostingEmbedding,
)
from app.services.vector_search import cosine_similarity

logger = logging.getLogger(__name__)


async def get_preferences(db: AsyncSession, user_id: UUID) -> CandidateJobPreferences | None:
    result = await db.execute(
        select(CandidateJobPreferences).where(CandidateJobPreferences.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def upsert_preferences(
    db: AsyncSession, user_id: UUID, values: dict[str, object]
) -> CandidateJobPreferences:
    existing = await get_preferences(db, user_id)
    if existing:
        for key, value in values.items():
            setattr(existing, key, value)
        existing.updated_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(existing)
        return existing

    prefs = CandidateJobPreferences(user_id=user_id, **values)
    db.add(prefs)
    await db.commit()
    await db.refresh(prefs)
    return prefs


async def list_scan_enabled_preferences(
    db: AsyncSession, limit: int, offset: int
) -> list[CandidateJobPreferences]:
    """Used by the fan-out scheduler (§7.6) to page through candidates to scan."""
    result = await db.execute(
        select(CandidateJobPreferences)
        .where(CandidateJobPreferences.is_scan_enabled.is_(True))
        .order_by(CandidateJobPreferences.user_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def find_posting_by_dedup_key(db: AsyncSession, dedup_key: str) -> JobPosting | None:
    result = await db.execute(select(JobPosting).where(JobPosting.dedup_key == dedup_key))
    return result.scalar_one_or_none()


async def upsert_job_posting(
    db: AsyncSession, dedup_key: str, fields: dict[str, object], source: str
) -> JobPosting:
    existing = await find_posting_by_dedup_key(db, dedup_key)
    if existing:
        existing.last_seen_at = datetime.now(UTC)
        if source not in existing.sources_seen:
            existing.sources_seen = [*existing.sources_seen, source]
        existing.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    posting = JobPosting(dedup_key=dedup_key, sources_seen=[source], **fields)
    db.add(posting)
    await db.commit()
    await db.refresh(posting)
    return posting


async def store_posting_embedding(
    db: AsyncSession, job_posting_id: UUID, embedding: list[float], token_count: int
) -> None:
    existing = await db.execute(
        select(JobPostingEmbedding).where(JobPostingEmbedding.job_posting_id == job_posting_id)
    )
    row = existing.scalar_one_or_none()
    if row:
        row.embedding = embedding
        row.token_count = token_count
    else:
        db.add(
            JobPostingEmbedding(
                job_posting_id=job_posting_id, embedding=embedding, token_count=token_count
            )
        )
    await db.commit()


async def upsert_match(
    db: AsyncSession,
    user_id: UUID,
    job_posting_id: UUID,
    similarity_score: float,
    rule_score: float,
    overall_score: float,
    score_breakdown: dict[str, float],
) -> JobMatch:
    """INSERT or refresh score on conflict — see §5.4 unique (user_id, job_posting_id) index."""
    result = await db.execute(
        select(JobMatch).where(
            JobMatch.user_id == user_id, JobMatch.job_posting_id == job_posting_id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.similarity_score = similarity_score
        existing.rule_score = rule_score
        existing.overall_score = overall_score
        existing.score_breakdown = score_breakdown
        await db.commit()
        await db.refresh(existing)
        return existing

    match = JobMatch(
        user_id=user_id,
        job_posting_id=job_posting_id,
        similarity_score=similarity_score,
        rule_score=rule_score,
        overall_score=overall_score,
        score_breakdown=score_breakdown,
    )
    db.add(match)
    await db.commit()
    await db.refresh(match)
    return match


async def list_matches_for_user(
    db: AsyncSession, user_id: UUID, limit: int, offset: int
) -> tuple[list[tuple[JobMatch, JobPosting]], int]:
    result = await db.execute(
        select(JobMatch, JobPosting)
        .join(JobPosting, JobMatch.job_posting_id == JobPosting.id)
        .where(JobMatch.user_id == user_id)
        .order_by(JobMatch.overall_score.desc(), JobMatch.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = result.all()
    count_result = await db.execute(select(JobMatch).where(JobMatch.user_id == user_id))
    total = len(count_result.all())
    return [(m, p) for m, p in rows], total


async def get_top_unexplained_matches(
    db: AsyncSession, user_id: UUID, top_n: int
) -> list[tuple[JobMatch, JobPosting]]:
    """Top-N matches (by score) that don't have an LLM explanation yet — feeds Decision 1/3's LLM-last stage."""
    result = await db.execute(
        select(JobMatch, JobPosting)
        .join(JobPosting, JobMatch.job_posting_id == JobPosting.id)
        .where(JobMatch.user_id == user_id, JobMatch.explanation.is_(None))
        .order_by(JobMatch.overall_score.desc())
        .limit(top_n)
    )
    return [(m, p) for m, p in result.all()]


async def save_explanation(db: AsyncSession, match_id: UUID, explanation: str) -> None:
    await db.execute(
        update(JobMatch)
        .where(JobMatch.id == match_id)
        .values(explanation=explanation, explanation_generated_at=datetime.now(UTC))
    )
    await db.commit()


async def mark_notified(db: AsyncSession, match_ids: list[UUID]) -> None:
    if not match_ids:
        return
    await db.execute(
        update(JobMatch).where(JobMatch.id.in_(match_ids)).values(notified_at=datetime.now(UTC))
    )
    await db.commit()


async def count_unread_matches(db: AsyncSession, user_id: UUID) -> int:
    """Number of matches not yet viewed by the user — feeds the SSE unread-count push."""
    result = await db.execute(
        select(func.count())
        .select_from(JobMatch)
        .where(JobMatch.user_id == user_id, JobMatch.viewed_at.is_(None))
    )
    return int(result.scalar_one())


async def mark_viewed(db: AsyncSession, match_id: UUID, user_id: UUID) -> bool:
    result = await db.execute(
        update(JobMatch)
        .where(JobMatch.id == match_id, JobMatch.user_id == user_id, JobMatch.viewed_at.is_(None))
        .values(viewed_at=datetime.now(UTC))
    )
    await db.commit()
    return bool(result.rowcount > 0)  # type: ignore[attr-defined]


async def set_feedback(db: AsyncSession, match_id: UUID, user_id: UUID, feedback: str) -> bool:
    result = await db.execute(
        update(JobMatch)
        .where(JobMatch.id == match_id, JobMatch.user_id == user_id)
        .values(feedback=feedback)
    )
    await db.commit()
    return bool(result.rowcount > 0)  # type: ignore[attr-defined]


async def find_similar_postings(
    db: AsyncSession,
    query_embedding: list[float],
    limit: int = 20,
    similarity_threshold: float = 0.5,
    posting_ids: list[UUID] | None = None,
) -> list[tuple[UUID, float]]:
    """Return (job_posting_id, similarity_score) pairs for active job postings whose
    embedding is within similarity_threshold of query_embedding, restricted to
    posting_ids if given. Postgres: pgvector cosine similarity. SQLite: Python
    fallback using the same cosine_similarity() helper as vector_search.py.
    """
    settings = get_settings()
    is_postgres = "postgresql" in settings.database_url.lower()

    if is_postgres:
        # Use pgvector cosine similarity (1 - cosine_distance)
        # cosine_distance is <=> operator in pgvector
        # similarity = 1 - cosine_distance
        # Format embedding as PostgreSQL array string for pgvector
        # IMPORTANT: We pass this as a literal string, not a bound parameter,
        # because pgvector's ::vector cast doesn't work with parameter binding
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        query_stmt: Select[Any] = (
            select(
                JobPostingEmbedding.job_posting_id,
                # Use literal embedding string (not bound parameter) for pgvector compatibility
                literal_column(
                    f"(1 - (job_posting_embeddings.embedding <=> '{embedding_str}'::vector))"
                ).label("similarity"),
            )
            .join(JobPosting, JobPosting.id == JobPostingEmbedding.job_posting_id)
            .where(
                text(
                    f"(1 - (job_posting_embeddings.embedding <=> '{embedding_str}'::vector)) >= {similarity_threshold}"
                )
            )
            .where(JobPosting.is_active.is_(True))
        )

        if posting_ids:
            query_stmt = query_stmt.where(JobPosting.id.in_(posting_ids))

        query_stmt = query_stmt.order_by(text("similarity DESC")).limit(limit)

        try:
            result = await db.execute(query_stmt)
            rows = result.all()

            results: list[tuple[UUID, float]] = [
                (row.job_posting_id, float(row.similarity)) for row in rows
            ]

            logger.info(
                f"pgvector posting search found {len(results)} results",
                extra={
                    "num_results": len(results),
                    "threshold": similarity_threshold,
                    "num_posting_ids": len(posting_ids) if posting_ids else None,
                },
            )

            return results

        except Exception as e:
            logger.error(
                "pgvector posting search failed, falling back to Python implementation",
                extra={"error": str(e)},
                exc_info=True,
            )
            # Fall through to Python implementation

    # SQLite fallback: fetch all embeddings and compute similarity in Python
    logger.info("Using Python-based cosine similarity for postings (SQLite mode)")

    fallback_stmt = (
        select(JobPostingEmbedding)
        .join(JobPosting, JobPosting.id == JobPostingEmbedding.job_posting_id)
        .where(JobPosting.is_active.is_(True))
    )
    if posting_ids:
        fallback_stmt = fallback_stmt.where(JobPosting.id.in_(posting_ids))

    result = await db.execute(fallback_stmt)
    all_embeddings = result.scalars().all()

    # Compute similarities
    scored_results: list[tuple[float, JobPostingEmbedding]] = []
    for emb in all_embeddings:
        similarity = cosine_similarity(query_embedding, emb.embedding)
        if similarity >= similarity_threshold:
            scored_results.append((similarity, emb))

    # Sort by similarity descending
    scored_results.sort(key=lambda x: x[0], reverse=True)

    # Take top N
    top_results = scored_results[:limit]

    results = [(emb.job_posting_id, similarity) for similarity, emb in top_results]

    logger.info(
        f"Python posting similarity search found {len(results)} results",
        extra={
            "total_checked": len(all_embeddings),
            "num_results": len(results),
            "threshold": similarity_threshold,
        },
    )

    return results
