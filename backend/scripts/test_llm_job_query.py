"""Integration test for LLM job query optimization with real LiteLLM proxy.

Run this script to test LLM-powered job query optimization against actual Gemini API.

Usage:
    python backend/scripts/test_llm_job_query.py
"""

import asyncio
import json
import os
import sys

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.clients.llm import litellm_optimize_job_query
from app.core.config import get_settings


async def test_optimization(job_title: str, location: str | None, country: str | None) -> None:
    """Test LLM optimization with given parameters."""
    print(f"\n{'=' * 80}")
    print(f"Testing: job_title='{job_title}', location='{location}', country='{country}'")
    print(f"{'=' * 80}")

    settings = get_settings()

    # Display settings
    print("\nSettings:")
    print(f"  LLM_MODE: {settings.llm_mode}")
    print(f"  LITELLM_API_BASE: {settings.litellm_api_base}")
    print(f"  LITELLM_MODEL: {settings.litellm_model}")
    print(f"  LITELLM_FALLBACKS: {settings.litellm_fallbacks or '(none)'}")

    if settings.llm_mode != "litellm":
        print(f"\nERROR: LLM_MODE must be 'litellm' (currently: {settings.llm_mode})")
        print("Set LLM_MODE=litellm in .env.production or environment")
        return

    if not settings.litellm_api_base:
        print("\nERROR: LITELLM_API_BASE not configured")
        return

    # Call LLM optimization
    print("\nCalling LiteLLM for query optimization...")
    try:
        result = await litellm_optimize_job_query(job_title, location, country, settings)

        if result is None:
            print("\nWARNING: LLM optimization returned None (fallback to manual logic)")
            return

        print("\nSUCCESS: LLM Optimization Successful!")
        print(f"\nOptimized queries for {len(result)} boards:")
        print(json.dumps(result, indent=2))

        # Validate each board
        print("\nValidation:")
        required_boards = {"linkedin", "indeed", "glassdoor", "google", "zip_recruiter"}
        if set(result.keys()) == required_boards:
            print("  PASS: All 5 boards present")
        else:
            missing = required_boards - set(result.keys())
            extra = set(result.keys()) - required_boards
            if missing:
                print(f"  FAIL: Missing boards: {missing}")
            if extra:
                print(f"  WARN: Extra boards: {extra}")

        # Check each board has valid structure
        board_checks = {
            "linkedin": ["search_term", "location"],
            "indeed": ["search_term", "location", "country_indeed"],
            "glassdoor": ["search_term", "location"],
            "google": ["google_search_term"],
            "zip_recruiter": ["search_term", "location"],
        }

        for board, expected_fields in board_checks.items():
            if board in result:
                board_data = result[board]
                missing_fields = [f for f in expected_fields if f not in board_data]
                if missing_fields:
                    print(f"  FAIL: {board}: missing fields {missing_fields}")
                else:
                    print(f"  PASS: {board}: all required fields present")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback

        traceback.print_exc()


async def main() -> None:
    """Run integration tests with various inputs."""
    print("=" * 80)
    print("LLM Job Query Optimization Integration Test")
    print("=" * 80)

    # Test cases
    test_cases = [
        # Test case 1: Indian city
        ("Backend Developer", "Bengaluru", "India"),
        # Test case 2: US city
        ("Software Engineer", "San Francisco", "USA"),
        # Test case 3: Location with state
        ("Data Scientist", "Bengaluru, Karnataka", "India"),
        # Test case 4: No country
        ("Frontend Developer", "London", None),
        # Test case 5: Common typo
        ("DevOps Engineer", "Bangalore", "India"),
    ]

    for job_title, location, country in test_cases:
        await test_optimization(job_title, location, country)
        await asyncio.sleep(1)  # Rate limiting

    print("\n" + "=" * 80)
    print("Integration tests complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
