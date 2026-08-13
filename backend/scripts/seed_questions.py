"""Seed interview questions database with diverse questions across roles and categories.

Generates 200+ questions covering:
- 4 job roles: software_engineer, data_scientist, product_manager, devops_engineer
- 2 categories: behavioral, technical
- 3 difficulties: easy, medium, hard

Uses the question_generator service with GPT-4o-mini.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.services.question_generator import (
    JobRole,
    QuestionCategory,
    QuestionDifficulty,
    generate_questions,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_existing_questions(session: AsyncSession) -> int:
    """Check how many questions already exist in the database.

    Args:
        session: Database session

    Returns:
        Count of existing questions
    """
    result = await session.execute(text("SELECT COUNT(*) FROM interview_questions"))
    count = result.scalar() or 0
    return count


async def insert_question(
    session: AsyncSession,
    question_data: dict,
    dialect_name: str,
) -> None:
    """Insert a single question into the database.

    Args:
        session: Database session
        question_data: Question data dict from generator
        dialect_name: Database dialect (postgresql or sqlite)
    """
    question_id = uuid4()
    now = datetime.now(UTC)

    if dialect_name == "postgresql":
        # PostgreSQL: use native array and JSONB types
        await session.execute(
            text("""
                INSERT INTO interview_questions (
                    id, question_text, question_category, difficulty,
                    job_roles, technologies, sample_answer, scoring_rubric,
                    source, usage_count, created_at
                ) VALUES (
                    :id, :question_text, :category, :difficulty,
                    :job_roles, :technologies, :sample_answer, :scoring_rubric,
                    :source, :usage_count, :created_at
                )
            """),
            {
                "id": question_id,
                "question_text": question_data["question_text"],
                "category": question_data["category"],
                "difficulty": question_data["difficulty"],
                "job_roles": question_data["job_roles"],
                "technologies": question_data["technologies"],
                "sample_answer": question_data["sample_answer"],
                "scoring_rubric": json.dumps(question_data["scoring_rubric"]),
                "source": "gpt-4o-mini",
                "usage_count": 0,
                "created_at": now,
            },
        )
    else:
        # SQLite: store arrays and JSONB as text
        await session.execute(
            text("""
                INSERT INTO interview_questions (
                    id, question_text, question_category, difficulty,
                    job_roles, technologies, sample_answer, scoring_rubric,
                    source, usage_count, created_at
                ) VALUES (
                    :id, :question_text, :category, :difficulty,
                    :job_roles, :technologies, :sample_answer, :scoring_rubric,
                    :source, :usage_count, :created_at
                )
            """),
            {
                "id": str(question_id),
                "question_text": question_data["question_text"],
                "category": question_data["category"],
                "difficulty": question_data["difficulty"],
                "job_roles": json.dumps(question_data["job_roles"]),
                "technologies": json.dumps(question_data["technologies"]),
                "sample_answer": question_data["sample_answer"],
                "scoring_rubric": json.dumps(question_data["scoring_rubric"]),
                "source": "gpt-4o-mini",
                "usage_count": 0,
                "created_at": now,
            },
        )


async def seed_questions() -> None:
    """Generate and seed interview questions into the database."""
    settings = get_settings()

    # Create async engine
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if questions already exist
        existing_count = await check_existing_questions(session)

        if existing_count > 0:
            logger.info(f"Found {existing_count} existing questions in database")
            response = input("Do you want to add more questions? (yes/no): ").strip().lower()
            if response not in ["yes", "y"]:
                logger.info("Skipping seed - questions already exist")
                return

        # Get database dialect
        dialect_name = session.bind.dialect.name if session.bind else "sqlite"
        logger.info(f"Using {dialect_name} database")

        # Define seeding configuration
        job_roles: list[JobRole] = [
            "software_engineer",
            "data_scientist",
            "product_manager",
            "devops_engineer",
        ]
        categories: list[QuestionCategory] = ["behavioral", "technical"]
        difficulties: list[QuestionDifficulty] = ["easy", "medium", "hard"]

        # Generate questions for each combination
        total_generated = 0
        total_tokens = {"input": 0, "output": 0}

        for role in job_roles:
            for category in categories:
                for difficulty in difficulties:
                    logger.info(f"Generating questions: {role} / {category} / {difficulty}")

                    try:
                        # Generate 5 questions per combination
                        questions, tokens = await generate_questions(
                            job_role=role,
                            category=category,
                            difficulty=difficulty,
                            settings=settings,
                            count=5,
                        )

                        # Insert questions
                        for question in questions:
                            await insert_question(session, question, dialect_name)
                            total_generated += 1

                        total_tokens["input"] += tokens["input_tokens"]
                        total_tokens["output"] += tokens["output_tokens"]

                        logger.info(
                            f"  Generated {len(questions)} questions "
                            f"(tokens: {tokens['input_tokens']} + {tokens['output_tokens']})"
                        )

                        # Commit after each batch
                        await session.commit()

                        # Small delay to avoid rate limiting
                        await asyncio.sleep(0.5)

                    except Exception as e:
                        logger.error(
                            f"Failed to generate questions for {role}/{category}/{difficulty}: {e}",
                            exc_info=True,
                        )
                        await session.rollback()
                        continue

        # Calculate cost (GPT-4o-mini pricing: $0.15/1M input, $0.60/1M output)
        cost = (total_tokens["input"] * 0.15 + total_tokens["output"] * 0.60) / 1_000_000

        logger.info(
            f"Successfully seeded {total_generated} questions\n"
            f"  Total tokens: {total_tokens['input']} input + {total_tokens['output']} output\n"
            f"  Estimated cost: ${cost:.4f}"
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_questions())
