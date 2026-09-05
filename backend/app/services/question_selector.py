"""Interview question selection with smart filtering and rotation.

Selects questions based on:
- Job role matching
- Difficulty level
- Recency (avoids questions attempted in last 7 days)
- Usage balancing (prioritizes less-used questions)
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

JobRole = Literal["software_engineer", "data_scientist", "product_manager", "devops_engineer"]

QuestionCategory = Literal["behavioral", "technical", "system_design"]

QuestionDifficulty = Literal["easy", "medium", "hard"]


async def select_questions(
    session: AsyncSession,
    user_id: UUID,
    job_role: JobRole,
    difficulty: QuestionDifficulty | None = None,
    category: QuestionCategory | None = None,
    count: int = 5,
    exclude_recent_days: int = 7,
) -> list[dict[str, object]]:
    """Select interview questions with smart filtering and rotation.

    Args:
        session: Database session
        user_id: User ID to exclude recently attempted questions
        job_role: Job role to filter by
        difficulty: Optional difficulty filter (easy, medium, hard)
        category: Optional category filter (behavioral, technical, system_design)
        count: Number of questions to return (default 5)
        exclude_recent_days: Exclude questions attempted in last N days (default 7)

    Returns:
        List of question dicts with keys: id, question_text, category, difficulty,
        job_roles, technologies, usage_count

    Example:
        >>> questions = await select_questions(
        ...     session=session,
        ...     user_id=uuid.UUID("..."),
        ...     job_role="software_engineer",
        ...     difficulty="medium",
        ...     category="technical",
        ...     count=3
        ... )
        >>> for q in questions:
        ...     print(f"{q['difficulty']}: {q['question_text'][:50]}...")
    """
    from app.models import InterviewQuestion
    from app.modules.sessions.models import QuestionAttempt

    # Build base query with job role filter
    dialect_name = session.bind.dialect.name if session.bind else "sqlite"

    if dialect_name == "postgresql":
        # PostgreSQL: use array contains operator
        base_conditions: list[ColumnElement[bool]] = [
            func.array_position(InterviewQuestion.job_roles, job_role).isnot(None)
        ]
    else:
        # SQLite: job_roles is stored as a JSON-encoded text array (e.g. '["a", "b"]").
        # Match on the quoted JSON string element to avoid partial-word false positives.
        base_conditions = [InterviewQuestion.job_roles.like(f'%"{job_role}"%')]

    # Add optional filters
    if difficulty:
        base_conditions.append(InterviewQuestion.difficulty == difficulty)

    if category:
        base_conditions.append(InterviewQuestion.question_category == category)

    # Exclude recently attempted questions
    cutoff_date = datetime.now(UTC) - timedelta(days=exclude_recent_days)

    recent_attempts_subquery = (
        select(QuestionAttempt.question_id)
        .where(
            and_(
                QuestionAttempt.user_id == user_id,
                QuestionAttempt.attempted_at >= cutoff_date,
                QuestionAttempt.question_id.isnot(None),
            )
        )
        .scalar_subquery()
    )

    base_conditions.append(InterviewQuestion.id.notin_(recent_attempts_subquery))
    # §5.1 leak guard: a candidate must never draw another candidate's
    # personalized-for-them questions into their own rotation.
    base_conditions.append(
        or_(
            InterviewQuestion.personalized_for_user_id.is_(None),
            InterviewQuestion.personalized_for_user_id == user_id,
        )
    )

    # Build final query: order by usage_count ASC (prioritize less-used), then random
    query = (
        select(InterviewQuestion)
        .where(and_(*base_conditions))
        .order_by(InterviewQuestion.usage_count.asc(), func.random())
        .limit(count)
    )

    result = await session.execute(query)
    questions = result.scalars().all()

    if not questions:
        logger.warning(
            "No questions found matching criteria",
            extra={
                "user_id": str(user_id),
                "job_role": job_role,
                "difficulty": difficulty,
                "category": category,
                "exclude_recent_days": exclude_recent_days,
            },
        )
        return []

    # Increment usage_count for selected questions
    question_ids = [q.id for q in questions]
    await session.execute(
        update(InterviewQuestion)
        .where(InterviewQuestion.id.in_(question_ids))
        .values(usage_count=InterviewQuestion.usage_count + 1)
    )

    # Convert to dicts for response
    question_dicts = [
        {
            "id": str(q.id),
            "question_text": q.question_text,
            "category": q.question_category,
            "difficulty": q.difficulty,
            "job_roles": q.job_roles,
            "technologies": q.technologies,
            "usage_count": q.usage_count,
        }
        for q in questions
    ]

    logger.info(
        "Selected interview questions",
        extra={
            "user_id": str(user_id),
            "job_role": job_role,
            "difficulty": difficulty,
            "category": category,
            "count": len(question_dicts),
        },
    )

    return question_dicts


async def get_question_stats(
    session: AsyncSession,
    job_role: JobRole | None = None,
) -> dict[str, int]:
    """Get question bank statistics.

    Args:
        session: Database session
        job_role: Optional job role filter

    Returns:
        Dict with counts by category and difficulty

    Example:
        >>> stats = await get_question_stats(session, job_role="software_engineer")
        >>> print(f"Total: {stats['total']}")
        >>> print(f"Behavioral: {stats['behavioral']}")
    """
    from app.models import InterviewQuestion

    dialect_name = session.bind.dialect.name if session.bind else "sqlite"

    # Base conditions
    conditions: list[ColumnElement[bool]] = []
    if job_role:
        if dialect_name == "postgresql":
            conditions.append(
                func.array_position(InterviewQuestion.job_roles, job_role).isnot(None)
            )
        else:
            conditions.append(InterviewQuestion.job_roles.like(f'%"{job_role}"%'))

    # Total count
    base_query = select(func.count()).select_from(InterviewQuestion)
    if conditions:
        base_query = base_query.where(and_(*conditions))

    total_result = await session.execute(base_query)
    total = total_result.scalar() or 0

    # Counts by category
    category_counts = {}
    for cat in ["behavioral", "technical", "system_design"]:
        cat_query = base_query.where(InterviewQuestion.question_category == cat)
        cat_result = await session.execute(cat_query)
        category_counts[cat] = cat_result.scalar() or 0

    # Counts by difficulty
    difficulty_counts = {}
    for diff in ["easy", "medium", "hard"]:
        diff_query = base_query.where(InterviewQuestion.difficulty == diff)
        diff_result = await session.execute(diff_query)
        difficulty_counts[diff] = diff_result.scalar() or 0

    return {
        "total": total,
        **category_counts,
        **difficulty_counts,
    }
