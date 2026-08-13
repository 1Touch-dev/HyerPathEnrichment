"""Manual test script for DSAR full data access feature."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.compliance.dsar import build_access_summary
from app.compliance.identifiers import hash_identifier
from app.database.session import SessionLocal
from app.domain.enrichment import EnrichmentRequest
from app.enrichers.pipeline import Pipeline


async def main() -> None:
    """Create test enrichment data and verify DSAR access returns full data."""
    test_email = "dsar-test@example.com"
    test_username = "dsartest"

    async with SessionLocal() as db:
        pipeline = Pipeline(db)

        print("\n=== Testing DSAR Full Data Access ===\n")
        print(f"1. Creating test enrichment job for {test_email}...")

        request = EnrichmentRequest(
            email=test_email,
            username=test_username,
            requested_tiers=["tier2"],
        )

        job = await pipeline.run(request)
        print(f"   ✓ Job created: {job.id}")
        print(f"   Status: {job.status}")

        print("\n2. Submitting DSAR access request...")
        identifier_hash = hash_identifier(test_email)
        summary = await build_access_summary(db, identifier_hash, test_email)

        print("\n3. DSAR Access Summary:")
        print(f"   Identifier: {summary.get('identifier_provided')}")
        print(f"   Job count: {summary.get('job_count')}")
        print(f"   Photo cached: {summary.get('photo_cached')}")
        print(f"   First job: {summary.get('first_job_at')}")
        print(f"   Last job: {summary.get('last_job_at')}")

        enriched_data = summary.get("enriched_data")
        if enriched_data:
            print("\n4. Enriched Data Found:")
            if enriched_data.get("photo"):
                print(f"   ✓ Photo: {enriched_data['photo'].get('source')}")
            if enriched_data.get("emails"):
                print(f"   ✓ Emails: {', '.join(enriched_data['emails'])}")
            if enriched_data.get("handles"):
                handles = enriched_data["handles"]
                print(f"   ✓ Handles: {len(handles)} social profiles")
                for handle in handles[:3]:
                    print(f"      - {handle.get('platform')}: @{handle.get('username')}")
            if enriched_data.get("sources"):
                print(f"   ✓ Sources: {', '.join(enriched_data['sources'])}")
            if enriched_data.get("verified_emails"):
                print(f"   ✓ Verified emails: {len(enriched_data['verified_emails'])}")
            if enriched_data.get("business"):
                business = enriched_data["business"]
                print(f"   ✓ Business: {business.get('name')}")
        else:
            print("\n4. No enriched data available")

        print("\n=== Test completed successfully! ===\n")


if __name__ == "__main__":
    asyncio.run(main())
