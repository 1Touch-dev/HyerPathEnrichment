"""AI-powered interview feedback generation using GPT-4o-mini.

Provides rubric-based scoring and detailed feedback for interview practice sessions.
Uses structured JSON outputs for reliable parsing.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TypedDict

import httpx

from app.clients.retry import with_transient_retry
from app.core.config import Settings

logger = logging.getLogger(__name__)

# Heuristic LLM estimate disclaimer — set on every CvImprovementResult so callers
# never present the ats_score as if it mirrors a real employer's ATS scoring system.
ATS_SCORE_METHODOLOGY = (
    "Heuristic LLM estimate — does not reflect any specific employer's real ATS scoring system."
)

_NUMBER_TOKEN_RE = re.compile(r"\d[\d,.]*%?")

# Rubric dimensions (each scored 0-25 points)
FEEDBACK_DIMENSIONS = {
    "clarity": "Clear expression of ideas without ambiguity",
    "technical_accuracy": "Correctness of technical concepts and terminology",
    "completeness": "Coverage of all relevant aspects of the question",
    "communication_skills": "Professional delivery and structured response",
}


class InterviewFeedback(TypedDict):
    """Structured feedback for an interview answer."""

    overall_score: float  # 0-100
    dimension_scores: dict[str, float]  # Each dimension 0-25
    strengths: list[str]  # 2-4 positive highlights
    improvements: list[str]  # 2-4 actionable suggestions
    detailed_feedback: str  # Comprehensive paragraph


# OpenAI Structured Outputs schema (response_format: json_schema, strict mode).
# Without this, plain `{"type": "json_object"}` mode only asks for *some* JSON
# in the system prompt's prose — gpt-4o-mini sometimes echoes the rubric's
# human-readable headings verbatim (e.g. "Overall Score", "Clarity" as a
# top-level key) instead of these exact snake_case keys. `_parse_feedback_response`
# then silently falls back to defaults (0 / {} / "") via `.get(key, default)`
# with no error, so scores looked "generated" but were empty/zero. `strict: true`
# makes the API itself guarantee this exact shape, eliminating the drift.
_FEEDBACK_JSON_SCHEMA: dict[str, object] = {
    "type": "json_schema",
    "json_schema": {
        "name": "interview_feedback",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "overall_score": {"type": "number"},
                "dimension_scores": {
                    "type": "object",
                    "properties": {
                        "clarity": {"type": "number"},
                        "technical_accuracy": {"type": "number"},
                        "completeness": {"type": "number"},
                        "communication_skills": {"type": "number"},
                    },
                    "required": [
                        "clarity",
                        "technical_accuracy",
                        "completeness",
                        "communication_skills",
                    ],
                    "additionalProperties": False,
                },
                "strengths": {"type": "array", "items": {"type": "string"}},
                "improvements": {"type": "array", "items": {"type": "string"}},
                "detailed_feedback": {"type": "string"},
            },
            "required": [
                "overall_score",
                "dimension_scores",
                "strengths",
                "improvements",
                "detailed_feedback",
            ],
            "additionalProperties": False,
        },
    },
}


FEEDBACK_SYSTEM_PROMPT = """
You are an expert interview coach evaluating candidate responses.

Evaluate the candidate's answer using this rubric (each dimension 0-25 points):

1. Clarity (0-25): How clearly the candidate expressed their ideas
   - 20-25: Crystal clear, no ambiguity
   - 15-19: Mostly clear with minor confusion
   - 10-14: Some unclear parts requiring clarification
   - 0-9: Confusing or incoherent

2. Technical Accuracy (0-25): Correctness of technical concepts
   - 20-25: Fully accurate with precise terminology
   - 15-19: Mostly accurate with minor errors
   - 10-14: Some significant errors or misconceptions
   - 0-9: Fundamentally incorrect understanding

3. Completeness (0-25): Coverage of the question's requirements
   - 20-25: Addresses all aspects thoroughly
   - 15-19: Covers most key points
   - 10-14: Missing several important aspects
   - 0-9: Incomplete or off-topic

4. Communication Skills (0-25): Professional delivery and structure
   - 20-25: Excellent structure, professional tone
   - 15-19: Good organization with minor issues
   - 10-14: Somewhat disorganized or unprofessional
   - 0-9: Poor structure or inappropriate tone

Provide your evaluation as JSON with exactly these keys:
- "dimension_scores": an object with keys "clarity", "technical_accuracy", "completeness", "communication_skills" (each 0-25)
- "overall_score": sum of the four dimension scores (0-100)
- "strengths": 2-4 concrete strengths (array of strings)
- "improvements": 2-4 actionable improvements (array of strings)
- "detailed_feedback": a comprehensive feedback paragraph (string)

Be constructive and specific. Focus on helping the candidate improve.
""".strip()


def _build_feedback_messages(question: str | None, answer: str) -> list[dict[str, str]]:
    """Build chat messages for feedback generation.

    Args:
        question: The interview question asked (None for general evaluation)
        answer: The candidate's response

    Returns:
        List of message dicts for OpenAI chat API
    """
    if question and question.strip():
        user_content = f"""
Question: {question}

Answer: {answer}

Evaluate this interview response and provide structured feedback.
""".strip()
    else:
        # No specific question - evaluate answer as a general interview response
        user_content = f"""
Answer: {answer}

Evaluate this interview response and provide structured feedback in JSON format. Since no specific question was provided, assess the response as a general demonstration of the candidate's communication skills, technical knowledge, and professional presentation.
""".strip()

    return [
        {"role": "system", "content": FEEDBACK_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _parse_feedback_response(content: str, *, strict: bool = False) -> InterviewFeedback:
    """Parse LLM response into structured feedback.

    Args:
        content: Raw LLM response text
        strict: If True, raise on parse errors. If False, return fallback.

    Returns:
        InterviewFeedback with validated scores

    Raises:
        ValueError: If strict=True and parsing fails
    """
    try:
        # Extract JSON from response
        start = content.index("{")
        end = content.rindex("}") + 1
        data = json.loads(content[start:end])

        # Validate and extract fields
        dimension_scores = data.get("dimension_scores", {})
        overall_score = float(data.get("overall_score", 0))

        # Clamp dimension scores to 0-25
        for dim in FEEDBACK_DIMENSIONS:
            if dim in dimension_scores:
                dimension_scores[dim] = max(0.0, min(25.0, float(dimension_scores[dim])))

        # Clamp overall score to 0-100
        overall_score = max(0.0, min(100.0, overall_score))

        # Extract lists with defaults
        strengths = data.get("strengths", [])
        improvements = data.get("improvements", [])
        detailed_feedback = data.get("detailed_feedback", "")

        if not isinstance(strengths, list):
            strengths = []
        if not isinstance(improvements, list):
            improvements = []
        if not isinstance(detailed_feedback, str):
            detailed_feedback = ""

        return InterviewFeedback(
            overall_score=overall_score,
            dimension_scores=dimension_scores,
            strengths=strengths,
            improvements=improvements,
            detailed_feedback=detailed_feedback,
        )

    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
        logger.warning("Failed to parse feedback response", exc_info=True)
        if strict:
            raise ValueError(f"Invalid feedback JSON structure: {e}") from e

        # Fallback response
        return InterviewFeedback(
            overall_score=50.0,
            dimension_scores={dim: 12.5 for dim in FEEDBACK_DIMENSIONS},
            strengths=["Response provided"],
            improvements=["Continue practicing interview skills"],
            detailed_feedback="Unable to generate detailed feedback. Please try again.",
        )


async def generate_interview_feedback(
    question: str | None,
    answer: str,
    settings: Settings,
) -> tuple[InterviewFeedback, dict[str, int]]:
    """Generate AI feedback for an interview answer using GPT-4o-mini.

    Args:
        question: The interview question asked (None for general evaluation)
        answer: The candidate's response
        settings: App settings with OpenAI API key

    Returns:
        Tuple of (feedback, token_usage)
        token_usage dict has 'input_tokens' and 'output_tokens' keys

    Raises:
        httpx.HTTPError: If API request fails after retries
        ValueError: If response parsing fails

    Example:
        >>> settings = get_settings()
        >>> feedback, tokens = await generate_interview_feedback(
        ...     "Explain REST APIs",
        ...     "REST is...",
        ...     settings
        ... )
        >>> print(f"Score: {feedback['overall_score']}/100")
        >>> print(f"Cost: ${(tokens['input_tokens'] * 0.15 + tokens['output_tokens'] * 0.60) / 1_000_000:.4f}")
    """
    if not answer.strip():
        logger.warning("Empty answer provided for feedback generation")
        fallback = InterviewFeedback(
            overall_score=0.0,
            dimension_scores={dim: 0.0 for dim in FEEDBACK_DIMENSIONS},
            strengths=[],
            improvements=["Provide a complete answer to the question"],
            detailed_feedback="No answer was provided.",
        )
        return fallback, {"input_tokens": 0, "output_tokens": 0}

    api_key = settings.openai_api_key.strip()
    if not api_key:
        logger.error("OpenAI API key not configured")
        raise ValueError("OpenAI API key not configured")

    messages = _build_feedback_messages(question, answer)

    # DEBUG, not INFO: contains the candidate's raw interview answer, which is
    # personal/sensitive content. Structured logging renders `extra=` fields
    # directly into the log stream (see core/logging.py's `_extra_fields`), so
    # this must not be at the default INFO level in staging/production.
    logger.debug(
        "Feedback generation request",
        extra={
            "question": question,
            "answer": answer,
        },
    )

    # Call OpenAI API with JSON mode
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
                    "response_format": _FEEDBACK_JSON_SCHEMA,
                    "temperature": 0.3,  # Lower temperature for consistent scoring
                },
            )
            resp.raise_for_status()
            return resp

        try:
            response = await with_transient_retry(_do_post)

            result = response.json()
            content = result["choices"][0]["message"]["content"]

            # DEBUG: the raw LLM response echoes back the candidate's answer
            # content inside `detailed_feedback`/quoted excerpts — same PII
            # concern as the request log above.
            logger.debug(
                "Feedback generation raw LLM response",
                extra={"raw_content": content},
            )

            # Extract token usage
            usage = result.get("usage", {})
            token_usage = {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            }

            feedback = _parse_feedback_response(content, strict=True)

            # Scores/token counts are safe at INFO (operationally useful, not
            # sensitive); `detailed_feedback` can quote the candidate's answer,
            # so it's logged separately at DEBUG only.
            logger.info(
                "Generated interview feedback",
                extra={
                    "overall_score": feedback["overall_score"],
                    "dimension_scores": feedback["dimension_scores"],
                    "input_tokens": token_usage["input_tokens"],
                    "output_tokens": token_usage["output_tokens"],
                    "question_length": len(question) if question else 0,
                    "answer_length": len(answer),
                },
            )
            logger.debug(
                "Generated interview feedback detail",
                extra={"detailed_feedback": feedback["detailed_feedback"]},
            )

            return feedback, token_usage

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


class CvImprovementResult(TypedDict):
    """Structured CV improvement suggestions (Decision 3)."""

    ats_score: int  # 0-100
    strengths: list[str]
    improvements: list[str]
    rewritten_bullets: list[dict[str, str]]  # [{original, rewritten, rationale}]
    ats_score_methodology: str


CV_IMPROVEMENT_SYSTEM_PROMPT = """
You are an expert resume coach and ATS (Applicant Tracking System) specialist.

Review the candidate's CV text and provide improvement suggestions. Focus on:
- ATS optimization: keyword alignment, standard section headers, no tables/columns that break parsers
- Impact quantification: rewrite vague bullets to include a measurable outcome where the source text
  supports it (do not invent numbers the candidate did not provide or imply)
- Clarity and action-verb-led phrasing

Return JSON with exactly these fields:
{
  "ats_score": <int 0-100>,
  "strengths": [<2-4 short strings>],
  "improvements": [<2-4 short, actionable strings>],
  "rewritten_bullets": [
    {"original": <exact text from the CV>, "rewritten": <improved version>, "rationale": <one sentence why>}
  ]
}

Only include bullets that genuinely benefit from rewriting (up to 5). Never fabricate metrics, employers,
or dates not present in the source text. If the CV text is too short or malformed to assess meaningfully,
return an ats_score of 0 and explain why in "improvements".
""".strip()


def _drop_fabricated_metric_bullets(bullets: list[dict[str, str]]) -> list[dict[str, str]]:
    """Drop bullets whose 'rewritten' text contains a number not present in 'original'.

    Guards against the LLM fabricating metrics despite the system prompt's
    instruction not to invent numbers absent from the source CV text.
    """
    kept: list[dict[str, str]] = []
    for bullet in bullets:
        rewritten_numbers = _NUMBER_TOKEN_RE.findall(bullet["rewritten"])
        original = bullet["original"]
        if all(number in original for number in rewritten_numbers):
            kept.append(bullet)
    return kept


def _parse_cv_improvement_response(content: str) -> CvImprovementResult:
    try:
        start = content.index("{")
        end = content.rindex("}") + 1
        data = json.loads(content[start:end])

        ats_score = max(0, min(100, int(data.get("ats_score", 0))))
        strengths = data.get("strengths", [])
        improvements = data.get("improvements", [])
        rewritten_bullets = data.get("rewritten_bullets", [])

        if not isinstance(strengths, list):
            strengths = []
        if not isinstance(improvements, list):
            improvements = []
        if not isinstance(rewritten_bullets, list):
            rewritten_bullets = []

        cleaned_bullets = [
            {
                "original": str(b.get("original", "")),
                "rewritten": str(b.get("rewritten", "")),
                "rationale": str(b.get("rationale", "")),
            }
            for b in rewritten_bullets
            if isinstance(b, dict) and b.get("original") and b.get("rewritten")
        ][:5]
        cleaned_bullets = _drop_fabricated_metric_bullets(cleaned_bullets)

        return CvImprovementResult(
            ats_score=ats_score,
            strengths=strengths[:4],
            improvements=improvements[:4],
            rewritten_bullets=cleaned_bullets,
            ats_score_methodology=ATS_SCORE_METHODOLOGY,
        )
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        logger.warning("Failed to parse CV improvement response", exc_info=True)
        return CvImprovementResult(
            ats_score=0,
            strengths=[],
            improvements=["Unable to generate CV feedback. Please try again."],
            rewritten_bullets=[],
            ats_score_methodology=ATS_SCORE_METHODOLOGY,
        )


async def generate_cv_improvement(
    cv_text: str,
    target_role: str | None,
    settings: Settings,
) -> tuple[CvImprovementResult, dict[str, int]]:
    """Generate AI CV-improvement suggestions using GPT-4o-mini (Decision 3).

    Mirrors generate_interview_feedback()'s exact calling convention: JSON-mode
    chat completion via raw httpx, response.json() called synchronously.

    Args:
        cv_text: Raw extracted CV text (CandidateDocument.raw_text)
        target_role: Optional role the candidate is optimizing for
        settings: App settings with OpenAI API key

    Returns:
        Tuple of (result, token_usage)
    """
    if not cv_text.strip():
        return (
            CvImprovementResult(
                ats_score=0,
                strengths=[],
                improvements=["No CV text available."],
                rewritten_bullets=[],
                ats_score_methodology=ATS_SCORE_METHODOLOGY,
            ),
            {"input_tokens": 0, "output_tokens": 0},
        )

    api_key = settings.openai_api_key.strip()
    if not api_key:
        raise ValueError("OpenAI API key not configured")

    role_line = f"\n\nTarget role: {target_role}" if target_role else ""
    user_content = f"CV text:\n{cv_text[:12000]}{role_line}"  # truncate defensively; GPT-4o-mini context is ample but bounded cost

    async with httpx.AsyncClient(timeout=60.0) as client:

        async def _do_post() -> httpx.Response:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": settings.cv_feedback_model,
                    "messages": [
                        {"role": "system", "content": CV_IMPROVEMENT_SYSTEM_PROMPT},
                        {"role": "user", "content": user_content},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,
                },
            )
            resp.raise_for_status()
            return resp

        response = await with_transient_retry(_do_post)
        result = response.json()  # synchronous — see §2.1 Bug 1
        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})
        token_usage = {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }
        parsed = _parse_cv_improvement_response(content)

        logger.info(
            "Generated CV improvement",
            extra={"ats_score": parsed["ats_score"], "input_tokens": token_usage["input_tokens"]},
        )
        return parsed, token_usage
