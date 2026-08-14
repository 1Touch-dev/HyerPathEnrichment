"""Unit tests for interview question bank services.

Tests:
- Question generation with mocked OpenAI API
- Question selection with filtering and recency exclusion
- Seed script with mocked API calls
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Self
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.question_generator import (
    _build_generation_messages,
    _parse_generation_response,
    generate_questions,
)
from app.services.question_selector import get_question_stats, select_questions


# Override DB setup fixture for this module
@pytest.fixture(scope="module", autouse=True)
def skip_db_setup():
    """Skip database migrations for these unit tests."""
    return


# Mock settings for tests
class MockSettings:
    openai_api_key = "test-api-key"


@pytest.fixture
def mock_settings():
    return MockSettings()


@pytest.fixture
def sample_question_response():
    """Sample OpenAI API response for question generation."""
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "question_text": "Describe a time when you had to resolve a conflict within your team.",
                            "category": "behavioral",
                            "difficulty": "medium",
                            "job_roles": ["software_engineer", "product_manager"],
                            "technologies": ["communication", "leadership"],
                            "sample_answer": "A strong answer would use the STAR format...",
                            "scoring_rubric": {
                                "situation": "Clearly describes the conflict context",
                                "resolution": "Shows proactive conflict resolution skills",
                                "outcome": "Demonstrates positive team impact",
                            },
                        }
                    )
                }
            }
        ],
        "usage": {
            "prompt_tokens": 150,
            "completion_tokens": 200,
        },
    }


@pytest.fixture
def sample_multi_question_response():
    """Sample OpenAI API response for multiple question generation."""
    return {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        [
                            {
                                "question_text": "What is REST API?",
                                "category": "technical",
                                "difficulty": "easy",
                                "job_roles": ["software_engineer"],
                                "technologies": ["REST", "HTTP", "API"],
                                "sample_answer": "REST is an architectural style...",
                                "scoring_rubric": {
                                    "accuracy": "Correctly defines REST principles",
                                    "completeness": "Covers key concepts",
                                },
                            },
                            {
                                "question_text": "Explain async/await in Python",
                                "category": "technical",
                                "difficulty": "medium",
                                "job_roles": ["software_engineer"],
                                "technologies": ["Python", "asyncio"],
                                "sample_answer": "Async/await enables concurrent programming...",
                                "scoring_rubric": {
                                    "accuracy": "Correctly explains async/await",
                                    "examples": "Provides code examples",
                                },
                            },
                        ]
                    )
                }
            }
        ],
        "usage": {
            "prompt_tokens": 200,
            "completion_tokens": 350,
        },
    }


async def _insert_attempt(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    question_id: uuid.UUID,
    created_at: datetime | None = None,
) -> None:
    """Insert a question_attempts row via raw SQL, using the ORM's hex UUID format.

    Writes to the real ``question_attempts`` table (migration 015), matching
    what ``session_manager.add_attempt()`` writes in production and what
    ``question_selector.py``'s recency-exclusion query reads from after the
    fix for phase2_module3.md §4.4/§4.6 (previously it read from the
    never-written ``interview_attempts`` table, making the exclusion a
    permanent no-op). ``session_id`` is an arbitrary UUID with no matching
    ``practice_sessions`` row — safe here because SQLite FK enforcement is
    off by default in this app (see app/database/session.py), and this test
    only exercises the recency query, not session-level joins.
    """
    await db.execute(
        text(
            """
            INSERT INTO question_attempts (
                id, session_id, user_id, question_id, response_type, attempted_at
            ) VALUES (
                :id, :session_id, :user_id, :question_id, :response_type, :attempted_at
            )
            """
        ),
        {
            "id": uuid.uuid4().hex,
            "session_id": uuid.uuid4().hex,
            "user_id": user_id.hex,
            "question_id": question_id.hex,
            "response_type": "text",
            "attempted_at": created_at or datetime.now(UTC),
        },
    )


async def _insert_question(
    db: AsyncSession,
    *,
    question_id: uuid.UUID,
    category: str = "technical",
    difficulty: str = "medium",
    job_roles: list[str] | None = None,
    technologies: list[str] | None = None,
    usage_count: int = 0,
) -> None:
    """Insert a question row via raw SQL matching migration 016's schema.

    Uses ``question_id.hex`` (no dashes) so the stored value matches the format
    SQLAlchemy's ORM Uuid type binds on SQLite, keeping id-based lookups
    (e.g. the usage_count update in ``select_questions``) consistent.
    """
    await db.execute(
        text(
            """
            INSERT INTO interview_questions (
                id, question_text, question_category, difficulty,
                job_roles, technologies, sample_answer, scoring_rubric,
                source, usage_count, created_at
            ) VALUES (
                :id, :question_text, :category, :difficulty,
                :job_roles, :technologies, :sample_answer, :scoring_rubric,
                :source, :usage_count, :created_at
            )
            """
        ),
        {
            "id": question_id.hex,
            "question_text": f"Sample question {question_id}",
            "category": category,
            "difficulty": difficulty,
            "job_roles": json.dumps(job_roles or ["software_engineer"]),
            "technologies": json.dumps(technologies or ["python"]),
            "sample_answer": "Sample answer",
            "scoring_rubric": json.dumps({"criteria": "clarity"}),
            "source": "test",
            "usage_count": usage_count,
            "created_at": datetime.now(UTC),
        },
    )


class TestQuestionGeneration:
    """Test question generation service."""

    def test_build_generation_messages(self):
        """Test message building for different question types."""
        messages = _build_generation_messages(
            job_role="software_engineer",
            category="technical",
            difficulty="medium",
            count=1,
        )

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        # Use case-insensitive checks for content
        content = messages[1]["content"].lower()
        assert "software" in content and "engineer" in content
        assert "technical" in content
        assert "medium" in content

    def test_parse_single_question_response(self, sample_question_response):
        """Test parsing single question from API response."""
        content = sample_question_response["choices"][0]["message"]["content"]
        questions = _parse_generation_response(content, expected_count=1)

        assert len(questions) == 1
        question = questions[0]

        assert (
            question["question_text"]
            == "Describe a time when you had to resolve a conflict within your team."
        )
        assert question["category"] == "behavioral"
        assert question["difficulty"] == "medium"
        assert "software_engineer" in question["job_roles"]
        assert "product_manager" in question["job_roles"]
        assert len(question["technologies"]) > 0
        assert len(question["sample_answer"]) > 0
        assert isinstance(question["scoring_rubric"], dict)

    def test_parse_multi_question_response(self, sample_multi_question_response):
        """Test parsing multiple questions from API response."""
        content = sample_multi_question_response["choices"][0]["message"]["content"]
        questions = _parse_generation_response(content, expected_count=2)

        assert len(questions) == 2

        assert questions[0]["question_text"] == "What is REST API?"
        assert questions[0]["difficulty"] == "easy"

        assert questions[1]["question_text"] == "Explain async/await in Python"
        assert questions[1]["difficulty"] == "medium"

    def test_parse_invalid_response(self):
        """Test parsing invalid JSON response."""
        with pytest.raises(ValueError, match="Invalid question generation JSON structure"):
            _parse_generation_response("not json", expected_count=1)

    def test_parse_missing_fields(self):
        """Test parsing response with missing required fields."""
        invalid_content = json.dumps(
            {
                "question_text": "Test question",
                # Missing category, difficulty, etc.
            }
        )

        with pytest.raises(ValueError, match="Missing or invalid"):
            _parse_generation_response(invalid_content, expected_count=1)

    @pytest.mark.asyncio
    async def test_generate_questions_success(self, mock_settings, sample_question_response):
        """Test successful question generation."""
        with patch("httpx.AsyncClient") as mock_client:
            # Mock the async context manager and response
            mock_response = MagicMock()
            mock_response.json.return_value = sample_question_response
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            questions, tokens = await generate_questions(
                job_role="software_engineer",
                category="behavioral",
                difficulty="medium",
                settings=mock_settings,
                count=1,
            )

            # Verify results
            assert len(questions) == 1
            assert tokens["input_tokens"] == 150
            assert tokens["output_tokens"] == 200

            # Verify API call was made with correct parameters
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert call_args[0][0] == "https://api.openai.com/v1/chat/completions"
            assert call_args[1]["json"]["model"] == "gpt-4o-mini"
            assert call_args[1]["json"]["temperature"] == 0.8
            assert call_args[1]["headers"]["Authorization"] == "Bearer test-api-key"

    @pytest.mark.asyncio
    async def test_generate_multiple_questions(self, mock_settings, sample_multi_question_response):
        """Test generating multiple questions in one call."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = sample_multi_question_response
            mock_response.raise_for_status = MagicMock()

            mock_post = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.post = mock_post

            questions, _tokens = await generate_questions(
                job_role="software_engineer",
                category="technical",
                difficulty="medium",
                settings=mock_settings,
                count=2,
            )

            assert len(questions) == 2
            assert questions[0]["difficulty"] == "easy"
            assert questions[1]["difficulty"] == "medium"

    @pytest.mark.asyncio
    async def test_generate_questions_invalid_count(self, mock_settings):
        """Test generation with invalid count parameter."""
        with pytest.raises(ValueError, match="count must be between 1 and 5"):
            await generate_questions(
                job_role="software_engineer",
                category="technical",
                difficulty="medium",
                settings=mock_settings,
                count=10,  # Invalid: too high
            )

    @pytest.mark.asyncio
    async def test_generate_questions_missing_api_key(self):
        """Test generation with missing API key."""
        settings = MockSettings()
        settings.openai_api_key = ""

        with pytest.raises(ValueError, match="OpenAI API key not configured"):
            await generate_questions(
                job_role="software_engineer",
                category="technical",
                difficulty="medium",
                settings=settings,
                count=1,
            )

    @pytest.mark.asyncio
    async def test_generate_questions_api_error(self, mock_settings):
        """Test handling of API errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Invalid API key"

            from httpx import HTTPStatusError, Request

            mock_post = AsyncMock(
                side_effect=HTTPStatusError(
                    "401 Unauthorized",
                    request=MagicMock(spec=Request),
                    response=mock_response,
                )
            )
            mock_client.return_value.__aenter__.return_value.post = mock_post

            with pytest.raises(HTTPStatusError):
                await generate_questions(
                    job_role="software_engineer",
                    category="technical",
                    difficulty="medium",
                    settings=mock_settings,
                    count=1,
                )


class TestQuestionSelector:
    """Test question selection service."""

    @pytest.mark.asyncio
    async def test_select_questions_basic(self, db: AsyncSession):
        """Test basic question selection against a real (SQLite) database."""

        q1 = uuid.uuid4()
        q2 = uuid.uuid4()
        q3 = uuid.uuid4()

        await _insert_question(
            db,
            question_id=q1,
            category="technical",
            difficulty="medium",
            job_roles=["software_engineer"],
        )
        await _insert_question(
            db,
            question_id=q2,
            category="behavioral",
            difficulty="easy",
            job_roles=["software_engineer", "product_manager"],
        )
        await _insert_question(
            db,
            question_id=q3,
            category="technical",
            difficulty="hard",
            job_roles=["data_scientist"],  # different role, should never match
        )

        results = await select_questions(
            db, user_id=uuid.uuid4(), job_role="software_engineer", count=5
        )

        result_ids = {r["id"] for r in results}
        assert str(q1) in result_ids
        assert str(q2) in result_ids
        assert str(q3) not in result_ids  # wrong job role, must be excluded

        matched = next(r for r in results if r["id"] == str(q1))
        assert matched["category"] == "technical"
        assert matched["difficulty"] == "medium"
        assert matched["job_roles"] == ["software_engineer"]
        assert matched["usage_count"] == 1  # incremented by select_questions

    @pytest.mark.asyncio
    async def test_select_questions_filters_recent(self, db: AsyncSession):
        """Test that selector excludes questions attempted in the last N days."""

        user_id = uuid.uuid4()
        recent_question = uuid.uuid4()
        fresh_question = uuid.uuid4()

        await _insert_question(db, question_id=recent_question, job_roles=["devops_engineer"])
        await _insert_question(db, question_id=fresh_question, job_roles=["devops_engineer"])
        # Attempted 2 days ago - within the default 7-day exclusion window
        await _insert_attempt(
            db,
            user_id=user_id,
            question_id=recent_question,
            created_at=datetime.now(UTC) - timedelta(days=2),
        )

        results = await select_questions(db, user_id=user_id, job_role="devops_engineer", count=5)

        result_ids = {r["id"] for r in results}
        assert str(recent_question) not in result_ids
        assert str(fresh_question) in result_ids

        # A different user isn't affected by the first user's attempt history
        other_results = await select_questions(
            db, user_id=uuid.uuid4(), job_role="devops_engineer", count=5
        )
        other_ids = {r["id"] for r in other_results}
        assert str(recent_question) in other_ids

    @pytest.mark.asyncio
    async def test_select_questions_by_difficulty(self, db: AsyncSession):
        """Test filtering by difficulty level."""

        easy_q = uuid.uuid4()
        medium_q = uuid.uuid4()
        hard_q = uuid.uuid4()

        await _insert_question(
            db, question_id=easy_q, difficulty="easy", job_roles=["data_scientist"]
        )
        await _insert_question(
            db, question_id=medium_q, difficulty="medium", job_roles=["data_scientist"]
        )
        await _insert_question(
            db, question_id=hard_q, difficulty="hard", job_roles=["data_scientist"]
        )

        results = await select_questions(
            db,
            user_id=uuid.uuid4(),
            job_role="data_scientist",
            difficulty="medium",
            count=5,
        )

        assert len(results) == 1
        assert results[0]["id"] == str(medium_q)
        assert all(r["difficulty"] == "medium" for r in results)

    @pytest.mark.asyncio
    async def test_select_questions_by_category(self, db: AsyncSession):
        """Test filtering by question category."""

        behavioral_q = uuid.uuid4()
        technical_q = uuid.uuid4()

        await _insert_question(
            db, question_id=behavioral_q, category="behavioral", job_roles=["product_manager"]
        )
        await _insert_question(
            db, question_id=technical_q, category="technical", job_roles=["product_manager"]
        )

        results = await select_questions(
            db,
            user_id=uuid.uuid4(),
            job_role="product_manager",
            category="behavioral",
            count=5,
        )

        assert len(results) == 1
        assert results[0]["id"] == str(behavioral_q)
        assert results[0]["category"] == "behavioral"

    @pytest.mark.asyncio
    async def test_select_questions_returns_empty_list_when_nothing_matches(self, db: AsyncSession):
        """No questions match the requested job role -> empty list, no error."""

        results = await select_questions(
            db,
            user_id=uuid.uuid4(),
            job_role="devops_engineer",
            category="system_design",
            count=5,
        )

        assert results == []


class TestQuestionStats:
    """Test question bank statistics."""

    @pytest.mark.asyncio
    async def test_get_question_stats_totals_by_category_and_difficulty(self, db: AsyncSession):
        await _insert_question(
            db,
            question_id=uuid.uuid4(),
            category="technical",
            difficulty="easy",
            job_roles=["software_engineer"],
        )
        await _insert_question(
            db,
            question_id=uuid.uuid4(),
            category="behavioral",
            difficulty="medium",
            job_roles=["software_engineer"],
        )

        stats = await get_question_stats(db)

        assert stats["total"] >= 2
        assert stats["technical"] >= 1
        assert stats["behavioral"] >= 1
        assert stats["easy"] >= 1
        assert stats["medium"] >= 1
        assert set(stats.keys()) == {
            "total",
            "behavioral",
            "technical",
            "system_design",
            "easy",
            "medium",
            "hard",
        }

    @pytest.mark.asyncio
    async def test_get_question_stats_filters_by_job_role(self, db: AsyncSession):
        await _insert_question(
            db,
            question_id=uuid.uuid4(),
            category="technical",
            difficulty="hard",
            job_roles=["data_scientist"],
        )

        stats = await get_question_stats(db, job_role="data_scientist")
        assert stats["total"] >= 1

        stats_unrelated = await get_question_stats(db, job_role="product_manager")
        # A brand-new, unrelated role filter shouldn't pick up the data_scientist-only row.
        assert stats_unrelated["hard"] == 0 or stats_unrelated["total"] < stats["total"]


class TestSeedScript:
    """Test seed script functionality."""

    @pytest.mark.asyncio
    async def test_seed_questions_dry_run(self):
        """Test seed script generates & inserts the expected number of questions.

        Mocks generate_questions() and the DB session/engine so no real OpenAI
        API call or database connection happens.
        """
        from scripts import seed_questions as seed_module

        sample_question = {
            "question_text": "Sample question?",
            "category": "technical",
            "difficulty": "medium",
            "job_roles": ["software_engineer"],
            "technologies": ["python"],
            "sample_answer": "Sample answer",
            "scoring_rubric": {"clarity": "Clear and concise"},
        }

        class _FakeSession:
            def __init__(self) -> None:
                self.bind = None
                self.commit = AsyncMock()
                self.rollback = AsyncMock()

            async def __aenter__(self) -> Self:
                return self

            async def __aexit__(self, *exc_info: object) -> bool:
                return False

        fake_session = _FakeSession()
        mock_engine = MagicMock()
        mock_engine.dispose = AsyncMock()

        with (
            patch.object(seed_module, "create_async_engine", return_value=mock_engine),
            patch.object(seed_module, "sessionmaker", return_value=lambda: fake_session),
            patch.object(seed_module, "check_existing_questions", AsyncMock(return_value=0)),
            patch.object(
                seed_module,
                "generate_questions",
                AsyncMock(
                    return_value=(
                        [sample_question],
                        {"input_tokens": 10, "output_tokens": 20},
                    )
                ),
            ) as mock_generate,
            patch.object(seed_module, "insert_question", AsyncMock()) as mock_insert,
            patch.object(seed_module.asyncio, "sleep", AsyncMock()),
        ):
            await seed_module.seed_questions()

        # 4 job roles * 2 categories * 3 difficulties = 24 generation calls,
        # each returning exactly one question to insert.
        expected_calls = 4 * 2 * 3
        assert mock_generate.await_count == expected_calls
        assert mock_insert.await_count == expected_calls
        mock_engine.dispose.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_insert_question_postgresql(self):
        """Test question insertion for PostgreSQL uses native list params."""
        from scripts.seed_questions import insert_question

        mock_session = AsyncMock()
        question_data = {
            "question_text": "What is a REST API?",
            "category": "technical",
            "difficulty": "easy",
            "job_roles": ["software_engineer", "devops_engineer"],
            "technologies": ["REST", "HTTP"],
            "sample_answer": "A REST API is an architectural style...",
            "scoring_rubric": {"accuracy": "Correctly defines REST"},
        }

        await insert_question(mock_session, question_data, "postgresql")

        mock_session.execute.assert_awaited_once()
        params = mock_session.execute.call_args.args[1]

        assert params["job_roles"] == ["software_engineer", "devops_engineer"]
        assert params["technologies"] == ["REST", "HTTP"]
        assert isinstance(params["job_roles"], list)
        assert isinstance(params["technologies"], list)
        assert isinstance(params["id"], uuid.UUID)  # native UUID, not stringified
        assert params["category"] == "technical"
        assert params["difficulty"] == "easy"
        assert params["scoring_rubric"] == json.dumps(question_data["scoring_rubric"])

    @pytest.mark.asyncio
    async def test_insert_question_sqlite(self):
        """Test question insertion for SQLite JSON-encodes array columns."""
        from scripts.seed_questions import insert_question

        mock_session = AsyncMock()
        question_data = {
            "question_text": "Explain async/await in Python",
            "category": "technical",
            "difficulty": "medium",
            "job_roles": ["software_engineer"],
            "technologies": ["Python", "asyncio"],
            "sample_answer": "Async/await enables concurrent programming...",
            "scoring_rubric": {"depth": "Thorough explanation"},
        }

        await insert_question(mock_session, question_data, "sqlite")

        mock_session.execute.assert_awaited_once()
        params = mock_session.execute.call_args.args[1]

        assert params["job_roles"] == json.dumps(["software_engineer"])
        assert params["technologies"] == json.dumps(["Python", "asyncio"])
        assert isinstance(params["job_roles"], str)
        assert isinstance(params["technologies"], str)
        assert isinstance(params["id"], str)  # stringified UUID for SQLite TEXT column
        assert params["scoring_rubric"] == json.dumps(question_data["scoring_rubric"])
