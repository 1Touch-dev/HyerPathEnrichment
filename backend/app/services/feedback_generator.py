"""AI-powered interview feedback generation using GPT-4o-mini.

Provides rubric-based scoring and detailed feedback for interview practice sessions.
Uses structured JSON outputs for reliable parsing.
"""

from __future__ import annotations

import json
import logging
from typing import TypedDict

import httpx

from app.core.config import Settings

logger = logging.getLogger(__name__)

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

Provide your evaluation in JSON format with:
- Specific dimension scores
- Overall score (sum of dimensions, 0-100)
- 2-4 concrete strengths
- 2-4 actionable improvements
- Detailed feedback paragraph

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

    # Call OpenAI API with JSON mode
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "response_format": {"type": "json_object"},
                    "temperature": 0.3,  # Lower temperature for consistent scoring
                },
            )
            response.raise_for_status()

            result = await response.json()
            content = result["choices"][0]["message"]["content"]

            # Extract token usage
            usage = result.get("usage", {})
            token_usage = {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            }

            feedback = _parse_feedback_response(content, strict=True)

            logger.info(
                "Generated interview feedback",
                extra={
                    "overall_score": feedback["overall_score"],
                    "input_tokens": token_usage["input_tokens"],
                    "output_tokens": token_usage["output_tokens"],
                    "question_length": len(question) if question else 0,
                    "answer_length": len(answer),
                },
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
