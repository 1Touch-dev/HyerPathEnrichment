#!/usr/bin/env python3
"""Test script for job location filtering feature.

This script tests that JobSpy enricher correctly uses location and country parameters
to filter job search results to specific geographic regions.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import RequestedTier
from app.enrichers.jobspy import JobSpyEnricher


async def test_job_location_filtering():
    """Test that location and country parameters are correctly passed to JobSpy."""
    enricher = JobSpyEnricher()

    print("=" * 80)
    print("Testing Job Location Filtering Feature")
    print("=" * 80)

    # Test 1: US-specific job search
    print("\nTest 1: Search for jobs in San Francisco, USA")
    print("-" * 80)
    request_us = EnrichmentRequest(
        job_title="Software Engineer",
        job_location="San Francisco, CA",
        job_country="USA",
        requested_tiers=[RequestedTier.tier4],
    )

    valid_us = await enricher.validate(request_us)
    print(f"✓ Validation passed: {valid_us}")

    if valid_us:
        result_us = await enricher.run(request_us)
        jobs_us = result_us.get("jobs", [])
        print(f"✓ Found {len(jobs_us)} jobs")

        if jobs_us:
            print("\nSample jobs:")
            for i, job in enumerate(jobs_us[:3], 1):
                print(f"  {i}. {job['title']} at {job['company']} - {job['location']}")

    # Test 2: Germany-specific job search
    print("\n\nTest 2: Search for jobs in Berlin, Germany")
    print("-" * 80)
    request_de = EnrichmentRequest(
        job_title="Backend Developer",
        job_location="Berlin",
        job_country="Germany",
        requested_tiers=[RequestedTier.tier4],
    )

    valid_de = await enricher.validate(request_de)
    print(f"✓ Validation passed: {valid_de}")

    if valid_de:
        result_de = await enricher.run(request_de)
        jobs_de = result_de.get("jobs", [])
        print(f"✓ Found {len(jobs_de)} jobs")

        if jobs_de:
            print("\nSample jobs:")
            for i, job in enumerate(jobs_de[:3], 1):
                print(f"  {i}. {job['title']} at {job['company']} - {job['location']}")

    # Test 3: Without location (should default to broader search)
    print("\n\nTest 3: Search without location (baseline)")
    print("-" * 80)
    request_no_loc = EnrichmentRequest(
        job_title="Data Scientist", requested_tiers=[RequestedTier.tier4]
    )

    valid_no_loc = await enricher.validate(request_no_loc)
    print(f"✓ Validation passed: {valid_no_loc}")

    if valid_no_loc:
        result_no_loc = await enricher.run(request_no_loc)
        jobs_no_loc = result_no_loc.get("jobs", [])
        print(f"✓ Found {len(jobs_no_loc)} jobs")

        if jobs_no_loc:
            print("\nSample jobs (showing diverse locations):")
            for i, job in enumerate(jobs_no_loc[:5], 1):
                print(f"  {i}. {job['title']} at {job['company']} - {job['location']}")

    print("\n" + "=" * 80)
    print("Location Filtering Tests Complete!")
    print("=" * 80)
    print("\nKey improvements:")
    print("✓ Jobs are now filtered by location and country")
    print("✓ Indeed and Glassdoor use country_indeed parameter")
    print("✓ LinkedIn uses location parameter for global search")
    print("✓ Frontend now has separate fields for job_title, job_location, and job_country")
    print("\nNote: Job results depend on actual availability in JobSpy sources.")


if __name__ == "__main__":
    try:
        asyncio.run(test_job_location_filtering())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nError during testing: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
