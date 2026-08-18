"""CV structured extraction service using OpenAI GPT-4o-mini.

Extracts structured data from CV/resume text using OpenAI's structured outputs API.
Includes completeness scoring and missing field tracking.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from app.core.config import Settings
from app.domain.candidate import CVData

logger = logging.getLogger(__name__)

CV_EXTRACTION_PROMPT = """
Extract structured data from this CV/resume.
Return valid JSON matching this schema.

If a field is missing from the CV, use null. Do not invent data.

Focus on:
- Contact info (name, email, phone, LinkedIn, GitHub)
- Technical and soft skills
- Work experience (roles, companies, years, industries)
- Education (degree, field, certifications)
- Job preferences (desired roles, locations, remote preference)

Be thorough but conservative - only extract what's clearly stated in the CV.
""".strip()


_REQUIRED_FIELDS = [
    "full_name",
    "email",
    "phone",
    "technical_skills",
    "total_years_experience",
    "current_role",
    "highest_degree",
]


def _calculate_completeness(cv_data: CVData) -> tuple[float, list[str]]:
    """Calculate completeness score and identify missing required fields.

    Args:
        cv_data: Extracted CV data

    Returns:
        Tuple of (completeness_score, missing_fields)
        Score is 0.0 to 1.0 based on non-null required fields.
    """
    missing = []
    present = 0

    for field in _REQUIRED_FIELDS:
        value = getattr(cv_data, field, None)
        # Check if field is present and non-empty
        if value is None or (isinstance(value, (list, str)) and not value):
            missing.append(field)
        else:
            present += 1

    score = present / len(_REQUIRED_FIELDS) if _REQUIRED_FIELDS else 1.0
    return score, missing


async def extract_cv_data(cv_text: str, settings: Settings) -> CVData:
    """Extract structured data from CV text using OpenAI GPT-4o-mini.

    Uses OpenAI's JSON mode for structured outputs.
    Falls back to empty CVData on API errors.

    Args:
        cv_text: Raw CV text (from PDF, DOCX, etc.)
        settings: App settings with OpenAI API key

    Returns:
        CVData with extracted fields and completeness score.

    Example:
        >>> settings = get_settings()
        >>> cv_data = await extract_cv_data("John Doe\\n...", settings)
        >>> print(f"Completeness: {cv_data.completeness_score:.2%}")
    """
    if not cv_text.strip():
        logger.warning("Empty CV text provided")
        return CVData(completeness_score=0.0, missing_fields=_REQUIRED_FIELDS)

    api_key = settings.openai_api_key.strip()
    if not api_key:
        logger.warning("OpenAI API key not configured; returning empty CVData")
        return CVData(completeness_score=0.0, missing_fields=_REQUIRED_FIELDS)

    # Build messages for OpenAI API
    messages = [
        {"role": "system", "content": CV_EXTRACTION_PROMPT},
        {
            "role": "user",
            "content": f"Extract structured data from this CV:\n\n{cv_text[:4000]}",
        },
    ]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    payload = {
        "model": "gpt-4o-mini",
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            raw_data: dict[str, Any] = json.loads(content)

            # Parse into CVData model
            cv_data = CVData(**raw_data)

            # Calculate completeness
            score, missing = _calculate_completeness(cv_data)
            cv_data.completeness_score = score
            cv_data.missing_fields = missing

            logger.info(
                "CV extraction successful",
                extra={
                    "completeness": f"{score:.2%}",
                    "missing_count": len(missing),
                },
            )

            return cv_data

    except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError, Exception) as exc:
        logger.error(
            "CV extraction failed",
            exc_info=True,
            extra={"error_type": type(exc).__name__},
        )
        # Return empty CVData on failure
        return CVData(completeness_score=0.0, missing_fields=_REQUIRED_FIELDS)
