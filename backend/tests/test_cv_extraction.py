"""Tests for CV structured extraction service."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.config import Settings
from app.domain.candidate import CVData
from app.services.cv_extractor import _calculate_completeness, extract_cv_data


def test_completeness_score_full_cv():
    """Complete CV scores 1.0."""
    cv_data = CVData(
        full_name="John Doe",
        email="john@example.com",
        phone="+1234567890",
        technical_skills=["Python", "FastAPI"],
        total_years_experience=5.0,
        current_role="Senior Engineer",
        highest_degree="Bachelor's",
    )

    score, missing = _calculate_completeness(cv_data)

    assert score == 1.0
    assert missing == []


def test_completeness_score_partial_cv():
    """Partial CV (70% complete) scores correctly."""
    cv_data = CVData(
        full_name="Jane Smith",
        email="jane@example.com",
        phone="+9876543210",
        technical_skills=["JavaScript", "React"],
        total_years_experience=3.0,
        # Missing: current_role, highest_degree
    )

    score, missing = _calculate_completeness(cv_data)

    # 5 out of 7 required fields = 0.714...
    assert 0.70 <= score <= 0.72
    assert "current_role" in missing
    assert "highest_degree" in missing
    assert len(missing) == 2


def test_completeness_score_minimal_cv():
    """Minimal CV with only name scores low."""
    cv_data = CVData(full_name="Bob Johnson")

    score, missing = _calculate_completeness(cv_data)

    # 1 out of 7 required fields
    assert score < 0.2
    assert len(missing) == 6


def test_completeness_score_empty_lists_count_as_missing():
    """Empty list values count as missing."""
    cv_data = CVData(
        full_name="Test User",
        email="test@example.com",
        phone="+1111111111",
        technical_skills=[],  # Empty list
        total_years_experience=2.0,
        current_role="Developer",
        highest_degree="Master's",
    )

    score, missing = _calculate_completeness(cv_data)

    assert "technical_skills" in missing
    assert score < 1.0


@pytest.mark.asyncio
async def test_extract_cv_data_success():
    """Successful CV extraction returns CVData."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": """{
                        "full_name": "Alice Williams",
                        "email": "alice@example.com",
                        "phone": "+1234567890",
                        "technical_skills": ["Python", "Django", "PostgreSQL"],
                        "total_years_experience": 7.0,
                        "current_role": "Staff Engineer",
                        "current_company": "Tech Corp",
                        "highest_degree": "Master's in CS"
                    }"""
                }
            }
        ]
    }

    settings = Settings(openai_api_key="test-key-123")

    with patch("app.services.cv_extractor.httpx.AsyncClient") as mock_client:
        mock_response_obj = AsyncMock()
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_response_obj.raise_for_status = lambda: None

        mock_post = AsyncMock(return_value=mock_response_obj)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await extract_cv_data("Sample CV text...", settings)

    assert isinstance(result, CVData)
    assert result.full_name == "Alice Williams"
    assert result.email == "alice@example.com"
    assert "Python" in result.technical_skills
    assert result.total_years_experience == 7.0
    assert result.completeness_score > 0.9


@pytest.mark.asyncio
async def test_extract_cv_data_incomplete_cv():
    """Incomplete CV extraction tracks missing fields."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": """{
                        "full_name": "Bob Smith",
                        "email": "bob@example.com"
                    }"""
                }
            }
        ]
    }

    settings = Settings(openai_api_key="test-key-123")

    with patch("app.services.cv_extractor.httpx.AsyncClient") as mock_client:
        mock_response_obj = AsyncMock()
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_response_obj.raise_for_status = lambda: None

        mock_post = AsyncMock(return_value=mock_response_obj)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await extract_cv_data("Minimal CV text...", settings)

    assert result.full_name == "Bob Smith"
    assert result.email == "bob@example.com"
    assert result.completeness_score < 0.5
    assert "phone" in result.missing_fields
    assert "technical_skills" in result.missing_fields
    assert "total_years_experience" in result.missing_fields


@pytest.mark.asyncio
async def test_extract_cv_data_empty_text():
    """Empty CV text returns empty CVData."""
    settings = Settings(openai_api_key="test-key-123")

    result = await extract_cv_data("", settings)

    assert isinstance(result, CVData)
    assert result.full_name is None
    assert result.completeness_score == 0.0
    assert len(result.missing_fields) == 7


@pytest.mark.asyncio
async def test_extract_cv_data_no_api_key():
    """Missing API key returns empty CVData without API call."""
    settings = Settings(openai_api_key="")

    result = await extract_cv_data("Sample CV text...", settings)

    assert isinstance(result, CVData)
    assert result.completeness_score == 0.0
    assert len(result.missing_fields) == 7


@pytest.mark.asyncio
async def test_extract_cv_data_api_error():
    """API errors return empty CVData."""
    settings = Settings(openai_api_key="test-key-123")

    with patch("app.services.cv_extractor.httpx.AsyncClient") as mock_client:
        mock_post = AsyncMock(side_effect=Exception("API Error"))
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await extract_cv_data("Sample CV text...", settings)

    assert isinstance(result, CVData)
    assert result.completeness_score == 0.0
    assert len(result.missing_fields) == 7


@pytest.mark.asyncio
async def test_extract_cv_data_malformed_response():
    """Malformed JSON response returns empty CVData."""
    mock_response = {"choices": [{"message": {"content": "Invalid JSON { this is broken"}}]}

    settings = Settings(openai_api_key="test-key-123")

    with patch("app.services.cv_extractor.httpx.AsyncClient") as mock_client:
        mock_response_obj = AsyncMock()
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_response_obj.raise_for_status = lambda: None

        mock_post = AsyncMock(return_value=mock_response_obj)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await extract_cv_data("Sample CV text...", settings)

    assert isinstance(result, CVData)
    assert result.completeness_score == 0.0


@pytest.mark.asyncio
async def test_extract_cv_data_with_preferences():
    """CV extraction includes job preferences."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": """{
                        "full_name": "Carol Davis",
                        "email": "carol@example.com",
                        "phone": "+5555555555",
                        "technical_skills": ["Java", "Spring Boot"],
                        "total_years_experience": 4.0,
                        "current_role": "Senior Developer",
                        "highest_degree": "Bachelor's",
                        "desired_roles": ["Tech Lead", "Engineering Manager"],
                        "desired_locations": ["San Francisco", "Remote"],
                        "remote_preference": "hybrid"
                    }"""
                }
            }
        ]
    }

    settings = Settings(openai_api_key="test-key-123")

    with patch("app.services.cv_extractor.httpx.AsyncClient") as mock_client:
        mock_response_obj = AsyncMock()
        mock_response_obj.json = AsyncMock(return_value=mock_response)
        mock_response_obj.raise_for_status = lambda: None

        mock_post = AsyncMock(return_value=mock_response_obj)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await extract_cv_data("CV with preferences...", settings)

    assert result.desired_roles == ["Tech Lead", "Engineering Manager"]
    assert result.desired_locations == ["San Francisco", "Remote"]
    assert result.remote_preference == "hybrid"
    assert result.completeness_score == 1.0


def test_industries_and_certifications_default_to_empty_list():
    """CVData defaults industries and certifications to empty lists when absent."""
    cv_data = CVData(full_name="Dana Lee")

    assert cv_data.industries == []
    assert cv_data.certifications == []


@pytest.mark.asyncio
async def test_extract_cv_data_with_industries_and_certifications():
    """CV extraction populates industries and certifications when present in the LLM response."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": """{
                        "full_name": "Erin Walsh",
                        "email": "erin@example.com",
                        "phone": "+4444444444",
                        "technical_skills": ["Python", "AWS"],
                        "total_years_experience": 6.0,
                        "current_role": "Cloud Architect",
                        "highest_degree": "Bachelor's",
                        "industries": ["Healthcare", "Fintech"],
                        "certifications": ["AWS Certified Solutions Architect", "PMP"]
                    }"""
                }
            }
        ]
    }

    settings = Settings(openai_api_key="test-key-123")

    with patch("app.services.cv_extractor.httpx.AsyncClient") as mock_client:
        mock_response_obj = AsyncMock()
        mock_response_obj.json = Mock(return_value=mock_response)
        mock_response_obj.raise_for_status = lambda: None

        mock_post = AsyncMock(return_value=mock_response_obj)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await extract_cv_data("CV with industries and certifications...", settings)

    assert result.industries == ["Healthcare", "Fintech"]
    assert result.certifications == ["AWS Certified Solutions Architect", "PMP"]
    assert result.completeness_score == 1.0


@pytest.mark.asyncio
async def test_extract_cv_data_without_industries_and_certifications_defaults_empty():
    """CV extraction defaults industries and certifications to empty lists when the LLM omits them."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": """{
                        "full_name": "Frank Ito",
                        "email": "frank@example.com"
                    }"""
                }
            }
        ]
    }

    settings = Settings(openai_api_key="test-key-123")

    with patch("app.services.cv_extractor.httpx.AsyncClient") as mock_client:
        mock_response_obj = AsyncMock()
        mock_response_obj.json = Mock(return_value=mock_response)
        mock_response_obj.raise_for_status = lambda: None

        mock_post = AsyncMock(return_value=mock_response_obj)
        mock_client.return_value.__aenter__.return_value.post = mock_post

        result = await extract_cv_data("Minimal CV text...", settings)

    assert result.full_name == "Frank Ito"
    assert result.industries == []
    assert result.certifications == []
