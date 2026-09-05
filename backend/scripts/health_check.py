#!/usr/bin/env python3
"""
Comprehensive health check for all enrichers and observability services.
"""

import asyncio
import sys

import httpx


async def check_service(name: str, url: str, expected_status: int = 200) -> dict:
    """Check if a service is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url)
            status = (
                "✅ UP"
                if response.status_code == expected_status
                else f"⚠️  HTTP {response.status_code}"
            )
            return {
                "service": name,
                "url": url,
                "status": status,
                "healthy": response.status_code == expected_status,
            }
    except httpx.TimeoutException:
        return {"service": name, "url": url, "status": "❌ TIMEOUT", "healthy": False}
    except httpx.ConnectError:
        return {"service": name, "url": url, "status": "❌ UNREACHABLE", "healthy": False}
    except Exception as e:
        return {
            "service": name,
            "url": url,
            "status": f"❌ ERROR: {type(e).__name__}",
            "healthy": False,
        }


async def check_reacher(url: str) -> dict:
    """Check Reacher with POST request."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{url}/v1/check_email",
                json={"to_email": "test@example.com", "from_email": "verify@test.com"},
            )
            status = (
                "✅ UP" if response.status_code in [200, 400] else f"⚠️  HTTP {response.status_code}"
            )
            return {"service": "Reacher (SMTP)", "url": url, "status": status, "healthy": True}
    except Exception as e:
        return {
            "service": "Reacher (SMTP)",
            "url": url,
            "status": f"❌ ERROR: {type(e).__name__}",
            "healthy": False,
        }


async def main():
    """Run all health checks."""

    print("\n" + "=" * 70)
    print("🏥 HYREPATH ENRICHMENT - HEALTH CHECK")
    print("=" * 70 + "\n")

    # Core Services
    print("📦 CORE SERVICES")
    print("-" * 70)
    core_checks = [
        check_service("API Server", "http://127.0.0.1:8000/health"),
        check_service(
            "Redis", "http://127.0.0.1:6379", expected_status=400
        ),  # Will fail but shows it's listening
        check_service("PostgreSQL", "http://127.0.0.1:5432", expected_status=400),
    ]
    core_results = await asyncio.gather(*core_checks)
    for result in core_results:
        print(f"{result['status']:20} {result['service']:30} {result['url']}")

    # Observability Stack
    print("\n📊 OBSERVABILITY STACK")
    print("-" * 70)
    obs_checks = [
        check_service("Langfuse (LLM Tracing)", "http://127.0.0.1:3002"),
        check_service("Glitchtip (Error Tracking)", "http://127.0.0.1:8001"),
        check_service("LiteLLM Proxy", "http://127.0.0.1:4000/health"),
    ]
    obs_results = await asyncio.gather(*obs_checks)
    for result in obs_results:
        print(f"{result['status']:20} {result['service']:30} {result['url']}")

    # Enricher Sidecars
    print("\n🔧 ENRICHER SIDECARS")
    print("-" * 70)
    enricher_checks = [
        check_service("Social Analyzer", "http://127.0.0.1:9005"),
        check_service("Email Verifier (AfterShip)", "http://127.0.0.1:8081"),
        check_service("Google Maps Scraper", "http://127.0.0.1:8080"),
        check_reacher("http://127.0.0.1:8082"),
        check_service("Change Detection", "http://127.0.0.1:5000"),
    ]
    enricher_results = await asyncio.gather(*enricher_checks)
    for result in enricher_results:
        print(f"{result['status']:20} {result['service']:30} {result['url']}")

    # Summary
    print("\n" + "=" * 70)
    all_results = core_results + obs_results + enricher_results
    healthy_count = sum(1 for r in all_results if r.get("healthy", False))
    total_count = len(all_results)

    print(f"SUMMARY: {healthy_count}/{total_count} services healthy")

    if healthy_count == total_count:
        print("✅ All systems operational!")
        return 0
    else:
        print(f"⚠️  {total_count - healthy_count} service(s) need attention")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
