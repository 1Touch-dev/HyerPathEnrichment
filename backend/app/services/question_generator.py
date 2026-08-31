"""AI-powered interview question generation using GPT-4o-mini.

Generates diverse interview questions across multiple dimensions:
- Job roles: software_engineer, data_scientist, product_manager, devops_engineer
- Categories: behavioral, technical, system_design
- Difficulties: easy, medium, hard

Uses structured JSON outputs for reliable parsing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Literal, TypedDict

import httpx

from app.clients.retry import with_transient_retry
from app.core.config import Settings

logger = logging.getLogger(__name__)

JobRole = Literal["software_engineer", "data_scientist", "product_manager", "devops_engineer"]

QuestionCategory = Literal["behavioral", "technical", "system_design"]

QuestionDifficulty = Literal["easy", "medium", "hard"]


@dataclass(slots=True)
class CandidateContext:
    """Optional personalization input (phase2_module3.md §3 Decision 1). All
    fields optional - partial résumé data (e.g. skills but no
    years_experience) still helps.
    """

    skills: list[str]
    target_role: str | None = None
    years_experience: int | None = None
    recent_job_titles: list[str] | None = None


class QuestionData(TypedDict):
    """Structured interview question data."""

    question_text: str
    category: QuestionCategory
    difficulty: QuestionDifficulty
    job_roles: list[JobRole]
    technologies: list[str]
    sample_answer: str
    scoring_rubric: dict[str, str]


@dataclass(slots=True)
class JobContext:
    """JD-tailored personalization input (Module 4, Module E). Distinct from
    CandidateContext (résumé-derived) — a JobContext always accompanies a
    CandidateContext when generating (both the JD and the résumé ground the
    question), but is never used alone.
    """

    job_description: str  # JobPosting.description_raw, truncated (see _MAX_JD_CHARS below)
    job_title: str
    company: str


_MAX_JD_CHARS = 3000  # generous excerpt — long enough for a full JD, short enough to
# keep prompt cost bounded; matches the existing precedent of
# workers/tasks/outreach.py's _get_job_description() truncating
# to description_raw[:1500] for the same cost-control reason,
# sized up here since question generation needs more of the JD's
# actual responsibilities/requirements text than an outreach
# email's brief "job description excerpt" context line does.


_CATEGORY_HINTS = {
    "behavioral": "past experiences, teamwork, conflict resolution, leadership",
    "technical": "coding, algorithms, system knowledge, debugging, best practices",
    "system_design": "architecture, scalability, trade-offs, components, data flow",
}

_DIFFICULTY_HINTS = {
    "easy": "entry-level or junior role, foundational concepts",
    "medium": "mid-level role, practical experience required",
    "hard": "senior or lead role, deep expertise and complex scenarios",
}


def _append_candidate_context_details(
    user_content: str, candidate_context: CandidateContext
) -> str:
    """Append the personalization-details paragraph to `user_content`, shared
    verbatim by both `_build_generation_messages` and `_build_jd_generation_messages`
    so the two prompts' résumé-personalization behavior stays in sync.
    """
    details = [
        (
            f"Tailor this question to a candidate with these skills: "
            f"{candidate_context.skills}. Prefer technologies and scenarios from "
            "this list where relevant to the category."
        )
    ]
    if candidate_context.target_role:
        details.append(f"Target role: {candidate_context.target_role}.")
    if candidate_context.years_experience is not None:
        details.append(f"Years of experience: {candidate_context.years_experience}.")
    if candidate_context.recent_job_titles:
        details.append(f"Recent job titles: {candidate_context.recent_job_titles}.")
    return user_content + "\n\n" + " ".join(details)


GENERATION_SYSTEM_PROMPT = """
You are an expert technical interviewer and hiring manager creating high-quality interview questions.

Generate interview questions that:
- Are clear, specific, and realistic
- Match the specified role, category, and difficulty level
- Include diverse technology stacks where applicable
- Have actionable scoring rubrics
- Provide comprehensive sample answers

For behavioral questions:
- Focus on past experience and situation handling
- Use STAR format hints (Situation, Task, Action, Result)
- Evaluate communication, leadership, teamwork, problem-solving

For technical questions:
- Test conceptual understanding and practical knowledge
- Cover relevant technologies and frameworks
- Include code examples where appropriate
- Assess depth of technical expertise

For system design questions:
- Focus on architecture, scalability, trade-offs
- Cover components, data flow, and reliability
- Test ability to think at scale
- Evaluate communication of technical decisions

Provide your response in JSON format with:
- question_text: The interview question
- category: One of [behavioral, technical, system_design]
- difficulty: One of [easy, medium, hard]
- job_roles: Array of applicable roles
- technologies: Array of relevant technologies/frameworks
- sample_answer: Comprehensive answer (200-400 words)
- scoring_rubric: Dict with 3-4 evaluation criteria

Be creative and diverse in your questions. Avoid generic or overly common questions.
""".strip()


def _build_generation_messages(
    job_role: JobRole,
    category: QuestionCategory,
    difficulty: QuestionDifficulty,
    count: int = 1,
    candidate_context: CandidateContext | None = None,
) -> list[dict[str, str]]:
    """Build chat messages for question generation.

    Args:
        job_role: Target job role
        category: Question category
        difficulty: Question difficulty
        count: Number of questions to generate
        candidate_context: Optional personalization input (§3 Decision 1). When
            provided, an extra paragraph is appended to the user prompt so the
            question is tailored to the candidate's résumé data. When None,
            the prompt content is byte-identical to the non-personalized path.

    Returns:
        List of message dicts for OpenAI chat API
    """
    role_descriptions = {
        "software_engineer": "Software Engineer (full-stack, backend, frontend, mobile)",
        "data_scientist": "Data Scientist (ML, analytics, data engineering)",
        "product_manager": "Product Manager (product strategy, roadmap, stakeholder management)",
        "devops_engineer": "DevOps Engineer (CI/CD, infrastructure, cloud, automation)",
    }

    category_hints = _CATEGORY_HINTS
    difficulty_hints = _DIFFICULTY_HINTS

    user_content = f"""
Generate {count} unique interview question{"s" if count > 1 else ""} with these specifications:

Role: {role_descriptions[job_role]}
Category: {category} ({category_hints[category]})
Difficulty: {difficulty} ({difficulty_hints[difficulty]})

Each question should be distinct and realistic for actual interviews.
{'Return a JSON object with a "questions" array containing ' + str(count) + " question objects." if count > 1 else "Return a single JSON object."}
""".strip()

    if candidate_context is not None:
        user_content = _append_candidate_context_details(user_content, candidate_context)

    return [
        {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _parse_generation_response(content: str, expected_count: int = 1) -> list[QuestionData]:
    """Parse LLM response into structured question data.

    Accepts a single question object, a raw JSON array, or the json_object-mode
    wrapper ``{"questions": [...]}`` that OpenAI returns when response_format is
    set to json_object.
    """
    try:
        # Prefer whichever JSON root appears first. A raw array like
        # ``[{...}, {...}]`` also contains ``{``, so checking for braces
        # first would slice from the first object to the last ``}`` and
        # ``json.loads`` would raise "Extra data".
        brace_idx = content.find("{")
        bracket_idx = content.find("[")
        if brace_idx == -1 and bracket_idx == -1:
            raise ValueError("No JSON object or array found in response")
        if bracket_idx != -1 and (brace_idx == -1 or bracket_idx < brace_idx):
            start = bracket_idx
            end = content.rindex("]") + 1
        else:
            start = brace_idx
            end = content.rindex("}") + 1
        data = json.loads(content[start:end])

        if isinstance(data, dict):
            if isinstance(data.get("questions"), list):
                data = data["questions"]
            else:
                data = [data]
        elif not isinstance(data, list):
            raise ValueError("Expected a JSON object or array")

        questions: list[QuestionData] = []

        for item in data:
            # Validate required fields
            if not isinstance(item.get("question_text"), str):
                raise ValueError("Missing or invalid question_text")
            if not isinstance(item.get("category"), str):
                raise ValueError("Missing or invalid category")
            if not isinstance(item.get("difficulty"), str):
                raise ValueError("Missing or invalid difficulty")
            if not isinstance(item.get("job_roles"), list):
                raise ValueError("Missing or invalid job_roles")
            if not isinstance(item.get("technologies"), list):
                raise ValueError("Missing or invalid technologies")
            if not isinstance(item.get("sample_answer"), str):
                raise ValueError("Missing or invalid sample_answer")
            if not isinstance(item.get("scoring_rubric"), dict):
                raise ValueError("Missing or invalid scoring_rubric")

            questions.append(
                QuestionData(
                    question_text=item["question_text"].strip(),
                    category=item["category"],
                    difficulty=item["difficulty"],
                    job_roles=item["job_roles"],
                    technologies=item["technologies"],
                    sample_answer=item["sample_answer"].strip(),
                    scoring_rubric=item["scoring_rubric"],
                )
            )

        if not questions:
            raise ValueError("No valid questions generated")

        return questions

    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
        logger.error("Failed to parse generation response", exc_info=True)
        raise ValueError(f"Invalid question generation JSON structure: {e}") from e


async def _call_and_parse(
    messages: list[dict[str, str]],
    count: int,
    api_key: str,
    job_role_for_logging: str,
) -> tuple[list[QuestionData], dict[str, int]]:
    """Shared tail of both `generate_questions` and `generate_jd_tailored_questions`:
    the httpx POST (via `with_transient_retry`), response parsing (via
    `_parse_generation_response`), and the `(questions, token_usage)` return
    contract. `job_role_for_logging` is only used for the info-log's `job_role`
    field — it's the target role for the non-JD path, and the JD's job title
    for the JD-tailored path — since there's no shared "role" concept between
    the two callers, only a loggable label.

    Extracted from `generate_questions`'s previous inline body (§9.3) — this
    refactor must not change `generate_questions`'s observable behavior (same
    retries, same error types, same logging).
    """
    async with httpx.AsyncClient(timeout=60.0) as client:

        async def _do_post() -> httpx.Response:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.8,  # Higher temperature for variety
                },
            )
            resp.raise_for_status()
            return resp

        try:
            response = await with_transient_retry(_do_post)

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # Extract token usage
            usage = result.get("usage", {})
            token_usage = {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            }

            questions = _parse_generation_response(content, expected_count=count)

            logger.info(
                "Generated interview questions",
                extra={
                    "job_role": job_role_for_logging,
                    "count": len(questions),
                    "input_tokens": token_usage["input_tokens"],
                    "output_tokens": token_usage["output_tokens"],
                },
            )

            return questions, token_usage

        except httpx.HTTPStatusError as e:
            logger.error(
                "OpenAI API request failed",
                extra={
                    "status_code": e.response.status_code,
                    "response": e.response.text[:500],
                },
                exc_info=True,
            )
            raise

        except (KeyError, IndexError) as e:
            logger.error("Invalid OpenAI API response structure", exc_info=True)
            raise ValueError(f"Invalid API response format: {e}") from e


async def generate_questions(
    job_role: JobRole,
    category: QuestionCategory,
    difficulty: QuestionDifficulty,
    settings: Settings,
    count: int = 1,
    candidate_context: CandidateContext | None = None,
) -> tuple[list[QuestionData], dict[str, int]]:
    """Generate interview questions using GPT-4o-mini.

    Args:
        job_role: Target job role
        category: Question category (behavioral, technical, system_design)
        difficulty: Question difficulty (easy, medium, hard)
        settings: App settings with OpenAI API key
        count: Number of questions to generate (default 1, max 15 per call)
        candidate_context: Optional personalization input (§3 Decision 1). When
            provided, the generated question is tailored toward the
            candidate's résumé data (skills/target role/experience). Defaults
            to None, which preserves today's non-personalized behavior exactly.

    Returns:
        Tuple of (questions, token_usage)
        token_usage dict has 'input_tokens' and 'output_tokens' keys

    Raises:
        httpx.HTTPError: If API request fails after retries
        ValueError: If response parsing fails or invalid parameters

    Example:
        >>> settings = get_settings()
        >>> questions, tokens = await generate_questions(
        ...     job_role="software_engineer",
        ...     category="technical",
        ...     difficulty="medium",
        ...     settings=settings,
        ...     count=3
        ... )
        >>> print(f"Generated {len(questions)} questions")
        >>> print(f"Cost: ${(tokens['input_tokens'] * 0.15 + tokens['output_tokens'] * 0.60) / 1_000_000:.4f}")
    """
    if count < 1 or count > 15:
        raise ValueError("count must be between 1 and 15")

    api_key = settings.openai_api_key.strip()
    if not api_key:
        logger.error("OpenAI API key not configured")
        raise ValueError("OpenAI API key not configured")

    messages = _build_generation_messages(job_role, category, difficulty, count, candidate_context)
    return await _call_and_parse(messages, count, api_key, job_role_for_logging=job_role)


def _build_jd_generation_messages(
    category: QuestionCategory,
    difficulty: QuestionDifficulty,
    job_context: JobContext,
    candidate_context: CandidateContext | None,
    count: int = 1,
) -> list[dict[str, str]]:
    """Builds the JD-tailored prompt. Reuses GENERATION_SYSTEM_PROMPT verbatim (the
    interviewer-persona instructions don't change), only the user-turn content differs:
    grounds the question in the JD's actual text first, then layers candidate résumé
    context on top exactly the way _build_generation_messages already does for the
    non-JD path — this keeps the two prompts structurally parallel rather than
    diverging into two unrelated prompt-engineering styles.
    """
    category_hints = _CATEGORY_HINTS
    difficulty_hints = _DIFFICULTY_HINTS

    jd_excerpt = job_context.job_description[:_MAX_JD_CHARS]
    user_content = f"""
Generate {count} unique interview question{"s" if count > 1 else ""} tailored SPECIFICALLY
to this job posting — not a generic question for the role in general.

Job title: {job_context.job_title}
Company: {job_context.company}
Job description: {jd_excerpt}

Category: {category} ({category_hints[category]})
Difficulty: {difficulty} ({difficulty_hints[difficulty]})

Ground the question in specific responsibilities, requirements, or technologies
actually mentioned in the job description above. Do not ask something that could
apply to any {job_context.job_title} role anywhere — it must be recognizably
about THIS posting.
{'Return a JSON object with a "questions" array containing ' + str(count) + " question objects." if count > 1 else "Return a single JSON object."}
""".strip()

    if candidate_context is not None:
        user_content = _append_candidate_context_details(user_content, candidate_context)

    return [
        {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


async def generate_jd_tailored_questions(
    job_context: JobContext,
    category: QuestionCategory,
    difficulty: QuestionDifficulty,
    settings: Settings,
    count: int = 1,
    candidate_context: CandidateContext | None = None,
) -> tuple[list[QuestionData], dict[str, int]]:
    """JD-tailored sibling of generate_questions(). Same HTTP call shape, retry
    policy (with_transient_retry), response parsing (_parse_generation_response
    is reused as-is — the response JSON shape is identical), and token-usage
    return contract — only the prompt-building step differs, via
    _build_jd_generation_messages instead of _build_generation_messages.
    """
    if count < 1 or count > 15:
        raise ValueError("count must be between 1 and 15")
    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise ValueError("OpenAI API key not configured")

    messages = _build_jd_generation_messages(
        category, difficulty, job_context, candidate_context, count
    )
    return await _call_and_parse(
        messages, count, api_key, job_role_for_logging=job_context.job_title
    )
