"""Insert a minimal question-bank fixture for smoke testing (no LLM calls).

Not part of the app; deliberately kept in scripts/ next to seed_questions.py as a
free/offline alternative for local smoke testing without an OpenAI key.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

import app.main  # noqa: F401 - importing registers every ORM class on Base.metadata
from app.models import InterviewQuestion

QUESTIONS = [
    ("Tell me about a time you disagreed with a teammate.", "behavioral", "medium"),
    ("How would you design a URL shortener?", "system_design", "hard"),
    ("Explain the difference between a list and a tuple in Python.", "technical", "easy"),
]


async def main() -> None:
    database_url = os.environ["DATABASE_URL"]
    engine = create_async_engine(database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        for question_text, category, difficulty in QUESTIONS:
            session.add(
                InterviewQuestion(
                    id=uuid4(),
                    question_text=question_text,
                    question_category=category,
                    difficulty=difficulty,
                    job_roles=["software_engineer"],
                    technologies=[],
                    sample_answer=None,
                    scoring_rubric=None,
                    source="smoke-test-fixture",
                    usage_count=0,
                    created_at=datetime.now(UTC),
                )
            )
        await session.commit()

    await engine.dispose()
    print(f"Inserted {len(QUESTIONS)} fixture questions.")


if __name__ == "__main__":
    asyncio.run(main())
