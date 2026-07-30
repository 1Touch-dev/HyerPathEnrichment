# Python Client Examples

Complete Python integration examples for the Hyrepath Enrichment API.

## Installation

```bash
pip install requests
```

## Authentication

All API requests require an API token in the `Authorization` header:

```python
API_TOKEN = "your-api-token-here"
BASE_URL = "https://enrich.hyrepath.io"  # or "http://localhost:8000" for dev

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}
```

---

## 1. Async Enrichment with Polling Loop

Submit an enrichment job and poll until completion.

```python
import requests
import time
from typing import Optional

API_TOKEN = "your-api-token-here"
BASE_URL = "https://enrich.hyrepath.io"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}


def create_enrichment_job(email: Optional[str] = None,
                          linkedin_url: Optional[str] = None,
                          tiers: list = None) -> str:
    """
    Submit an async enrichment job.
    Returns the job_id for polling.
    """
    if tiers is None:
        tiers = ["tier1", "tier2"]

    payload = {
        "email": email,
        "linkedin_url": linkedin_url,
        "requested_tiers": tiers
    }

    # Submit the job
    response = requests.post(
        f"{BASE_URL}/enrich",
        headers=headers,
        json=payload
    )
    response.raise_for_status()

    data = response.json()
    job_id = data["data"]["id"]
    print(f"✓ Job created: {job_id}")
    return job_id


def poll_job(job_id: str, poll_interval: int = 2, timeout: int = 300) -> dict:
    """
    Poll job status until completion or timeout.

    Args:
        job_id: The enrichment job ID
        poll_interval: Seconds between polls (default: 2)
        timeout: Maximum seconds to wait (default: 300)

    Returns:
        The completed job data with dossier
    """
    start_time = time.time()

    while True:
        # Check if we've exceeded timeout
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

        # Poll the job status
        response = requests.get(
            f"{BASE_URL}/enrich/{job_id}",
            headers=headers
        )
        response.raise_for_status()

        job_data = response.json()["data"]
        status = job_data["status"]

        print(f"  Status: {status} (elapsed: {elapsed:.1f}s)")

        # Terminal states
        if status == "completed":
            print("✓ Job completed successfully")
            return job_data
        elif status == "completed_no_data":
            print("⚠ Job completed but no data found")
            return job_data
        elif status == "failed":
            print("✗ Job failed")
            return job_data
        elif status == "suppressed":
            print("⚠ Job suppressed (opt-out)")
            return job_data

        # Still running, wait before next poll
        time.sleep(poll_interval)


def main():
    # Example 1: Enrich by email
    print("\n--- Example 1: Email enrichment ---")
    job_id = create_enrichment_job(
        email="john.doe@example.com",
        tiers=["tier1", "tier2", "tier3"]
    )
    result = poll_job(job_id)

    # Extract enriched data
    dossier = result.get("dossier", {})
    emails = dossier.get("emails", [])
    handles = dossier.get("handles", [])

    print(f"\nEnriched emails: {len(emails)}")
    print(f"Social handles: {len(handles)}")

    # Example 2: Enrich by LinkedIn URL
    print("\n--- Example 2: LinkedIn enrichment ---")
    job_id = create_enrichment_job(
        linkedin_url="https://www.linkedin.com/in/johndoe",
        tiers=["tier1"]
    )
    result = poll_job(job_id)


if __name__ == "__main__":
    main()
```

---

## 2. Sync Enrichment (Blocking)

Use the synchronous endpoint when you need immediate results.

```python
import requests

API_TOKEN = "your-api-token-here"
BASE_URL = "https://enrich.hyrepath.io"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}


def sync_enrichment(email: str = None, company: str = None, tiers: list = None):
    """
    Perform synchronous enrichment (blocks until complete).

    Note: May take 30-120s depending on tiers.
    """
    if tiers is None:
        tiers = ["tier1"]

    payload = {
        "email": email,
        "company": company,
        "requested_tiers": tiers
    }

    print("⏳ Waiting for enrichment (this may take 30-120s)...")

    # POST to /enrich/sync blocks until job completes
    response = requests.post(
        f"{BASE_URL}/enrich/sync",
        headers=headers,
        json=payload,
        timeout=180  # 3 minute timeout
    )
    response.raise_for_status()

    result = response.json()
    job_data = result["data"]

    print(f"✓ Job {job_data['id']} completed")
    return job_data


# Example usage
if __name__ == "__main__":
    result = sync_enrichment(
        email="jane.smith@acme.com",
        company="Acme Corp",
        tiers=["tier1", "tier2"]
    )

    dossier = result.get("dossier", {})
    print(f"\nEmails found: {dossier.get('emails', [])}")
    print(f"Verified emails: {len(dossier.get('verified_emails', []))}")
    print(f"Social handles: {len(dossier.get('handles', []))}")
```

---

## 3. Error Handling

Comprehensive error handling for all API responses.

```python
import requests
from requests.exceptions import HTTPError, Timeout, ConnectionError

API_TOKEN = "your-api-token-here"
BASE_URL = "https://enrich.hyrepath.io"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}


class EnrichmentAPIError(Exception):
    """Base exception for API errors."""
    def __init__(self, status_code: int, code: str, message: str, details=None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"{status_code} {code}: {message}")


def handle_api_error(response: requests.Response):
    """
    Parse and raise appropriate exceptions for API errors.
    """
    try:
        error_data = response.json()
        error = error_data.get("error", {})

        raise EnrichmentAPIError(
            status_code=error.get("status_code", response.status_code),
            code=error.get("code", "unknown"),
            message=error.get("message", "Unknown error"),
            details=error.get("details")
        )
    except ValueError:
        # Response body is not JSON
        raise EnrichmentAPIError(
            status_code=response.status_code,
            code="non_json_response",
            message=response.text or "Non-JSON error response"
        )


def safe_enrichment_request(email: str, tiers: list = None):
    """
    Make an enrichment request with comprehensive error handling.
    """
    if tiers is None:
        tiers = ["tier1"]

    payload = {
        "email": email,
        "requested_tiers": tiers
    }

    try:
        response = requests.post(
            f"{BASE_URL}/enrich",
            headers=headers,
            json=payload,
            timeout=30
        )

        # Check for HTTP errors
        if not response.ok:
            if response.status_code == 401:
                print("✗ Authentication failed")
                print("  → Check your API_TOKEN")
                handle_api_error(response)

            elif response.status_code == 422:
                print("✗ Validation error")
                print("  → Check request payload for missing/invalid fields")
                error = response.json().get("error", {})
                details = error.get("details")
                if details:
                    print(f"  → Details: {details}")
                handle_api_error(response)

            elif response.status_code == 429:
                print("✗ Rate limit exceeded")
                print("  → Wait before retrying (see common-errors.md for backoff)")
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    print(f"  → Retry after: {retry_after}s")
                handle_api_error(response)

            elif response.status_code == 503:
                print("✗ Service unavailable")
                print("  → Redis may be down, retry with exponential backoff")
                handle_api_error(response)

            else:
                handle_api_error(response)

        # Success
        data = response.json()
        job_id = data["data"]["id"]
        print(f"✓ Job created: {job_id}")
        return job_id

    except Timeout:
        print("✗ Request timeout")
        print("  → Check network connectivity or increase timeout")
        raise

    except ConnectionError:
        print("✗ Connection error")
        print("  → Check BASE_URL and network connectivity")
        raise

    except EnrichmentAPIError as e:
        print(f"✗ API Error: {e}")
        raise


# Example usage
if __name__ == "__main__":
    try:
        job_id = safe_enrichment_request(
            email="test@example.com",
            tiers=["tier1", "tier2"]
        )
        print(f"Success! Job ID: {job_id}")

    except EnrichmentAPIError as e:
        print(f"\nCaught API error:")
        print(f"  Status: {e.status_code}")
        print(f"  Code: {e.code}")
        print(f"  Message: {e.message}")
        if e.details:
            print(f"  Details: {e.details}")
```

---

## 4. Rate Limit Handling with Exponential Backoff

Handle 429 errors gracefully with automatic retry logic.

```python
import requests
import time
from typing import Optional

API_TOKEN = "your-api-token-here"
BASE_URL = "https://enrich.hyrepath.io"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}


def create_enrichment_with_retry(
    email: str,
    tiers: list = None,
    max_retries: int = 5,
    initial_backoff: float = 2.0
) -> str:
    """
    Create enrichment job with exponential backoff on rate limits.

    Args:
        email: Email to enrich
        tiers: List of tier strings (e.g., ["tier1", "tier2"])
        max_retries: Maximum number of retry attempts (default: 5)
        initial_backoff: Initial backoff delay in seconds (default: 2.0)

    Returns:
        job_id of created enrichment job
    """
    if tiers is None:
        tiers = ["tier1"]

    payload = {
        "email": email,
        "requested_tiers": tiers
    }

    backoff = initial_backoff

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                f"{BASE_URL}/enrich",
                headers=headers,
                json=payload,
                timeout=30
            )

            # Success
            if response.status_code == 202:
                data = response.json()
                job_id = data["data"]["id"]
                if attempt > 0:
                    print(f"✓ Succeeded after {attempt} retries")
                return job_id

            # Rate limit hit
            if response.status_code == 429:
                if attempt >= max_retries:
                    raise Exception(f"Rate limit exceeded after {max_retries} retries")

                # Check for Retry-After header
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    wait_time = float(retry_after)
                    print(f"⏳ Rate limited. Retry-After: {wait_time}s")
                else:
                    wait_time = backoff
                    print(f"⏳ Rate limited. Backing off for {wait_time:.1f}s")

                time.sleep(wait_time)

                # Exponential backoff (double the wait time)
                backoff *= 2
                continue

            # Other error
            response.raise_for_status()

        except requests.exceptions.Timeout:
            if attempt >= max_retries:
                raise
            print(f"⏳ Timeout. Retrying in {backoff:.1f}s...")
            time.sleep(backoff)
            backoff *= 2

    raise Exception("Max retries exceeded")


# Example usage
if __name__ == "__main__":
    # Test rate limit handling
    emails = [
        "user1@example.com",
        "user2@example.com",
        "user3@example.com",
    ]

    for email in emails:
        try:
            job_id = create_enrichment_with_retry(
                email=email,
                tiers=["tier1"],
                max_retries=5,
                initial_backoff=2.0
            )
            print(f"✓ Created job for {email}: {job_id}\n")

        except Exception as e:
            print(f"✗ Failed for {email}: {e}\n")
```

---

## 5. List All Jobs

Retrieve paginated list of enrichment jobs.

```python
import requests
from typing import List, Dict

API_TOKEN = "your-api-token-here"
BASE_URL = "https://enrich.hyrepath.io"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}


def list_jobs(limit: int = 20, offset: int = 0) -> Dict:
    """
    List enrichment jobs with pagination.

    Args:
        limit: Number of jobs per page (1-100, default: 20)
        offset: Offset for pagination (default: 0)

    Returns:
        Dict with 'jobs', 'total', 'limit', 'offset'
    """
    response = requests.get(
        f"{BASE_URL}/enrich",
        headers=headers,
        params={"limit": limit, "offset": offset}
    )
    response.raise_for_status()

    data = response.json()["data"]
    return data


def list_all_jobs() -> List[Dict]:
    """
    Retrieve all jobs by paginating through results.
    """
    all_jobs = []
    offset = 0
    limit = 100  # Max page size

    while True:
        page = list_jobs(limit=limit, offset=offset)
        jobs = page["jobs"]
        total = page["total"]

        all_jobs.extend(jobs)
        print(f"  Fetched {len(all_jobs)} / {total} jobs")

        # Check if we've fetched everything
        if len(all_jobs) >= total:
            break

        offset += limit

    return all_jobs


# Example usage
if __name__ == "__main__":
    # List first page
    print("--- First page of jobs ---")
    page = list_jobs(limit=10, offset=0)

    print(f"Total jobs: {page['total']}")
    print(f"Showing: {len(page['jobs'])} jobs\n")

    for job in page["jobs"]:
        print(f"Job {job['id']}")
        print(f"  Status: {job['status']}")
        print(f"  Created: {job['created_at']}")
        print(f"  Summary: {job.get('identifier_summary', 'N/A')}\n")

    # Fetch all jobs
    print("\n--- Fetching all jobs ---")
    all_jobs = list_all_jobs()
    print(f"✓ Retrieved {len(all_jobs)} total jobs")
```

---

## Complete Example: End-to-End Workflow

```python
import requests
import time
from typing import Optional, Dict

API_TOKEN = "your-api-token-here"
BASE_URL = "https://enrich.hyrepath.io"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}


class EnrichmentClient:
    """Complete enrichment client with all functionality."""

    def __init__(self, api_token: str, base_url: str = "https://enrich.hyrepath.io"):
        self.api_token = api_token
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }

    def create_job(self, email: str = None, linkedin_url: str = None,
                   company: str = None, tiers: list = None) -> str:
        """Create enrichment job."""
        if tiers is None:
            tiers = ["tier1"]

        payload = {
            "email": email,
            "linkedin_url": linkedin_url,
            "company": company,
            "requested_tiers": tiers
        }

        response = requests.post(
            f"{self.base_url}/enrich",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()

        return response.json()["data"]["id"]

    def get_job(self, job_id: str) -> Dict:
        """Get job status and results."""
        response = requests.get(
            f"{self.base_url}/enrich/{job_id}",
            headers=self.headers
        )
        response.raise_for_status()

        return response.json()["data"]

    def poll_until_complete(self, job_id: str, poll_interval: int = 2,
                           timeout: int = 300) -> Dict:
        """Poll job until completion."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            job = self.get_job(job_id)
            status = job["status"]

            if status in ["completed", "completed_no_data", "failed", "suppressed"]:
                return job

            time.sleep(poll_interval)

        raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")

    def enrich_sync(self, email: str = None, linkedin_url: str = None,
                    tiers: list = None) -> Dict:
        """Synchronous enrichment."""
        if tiers is None:
            tiers = ["tier1"]

        payload = {
            "email": email,
            "linkedin_url": linkedin_url,
            "requested_tiers": tiers
        }

        response = requests.post(
            f"{self.base_url}/enrich/sync",
            headers=self.headers,
            json=payload,
            timeout=180
        )
        response.raise_for_status()

        return response.json()["data"]


# Example usage
if __name__ == "__main__":
    client = EnrichmentClient(api_token=API_TOKEN)

    # Async workflow
    print("--- Async enrichment ---")
    job_id = client.create_job(
        email="john@example.com",
        tiers=["tier1", "tier2"]
    )
    print(f"Created job: {job_id}")

    result = client.poll_until_complete(job_id)
    print(f"Status: {result['status']}")

    # Sync workflow
    print("\n--- Sync enrichment ---")
    result = client.enrich_sync(
        email="jane@example.com",
        tiers=["tier1"]
    )
    print(f"Job completed: {result['id']}")
    print(f"Emails found: {len(result['dossier'].get('emails', []))}")
```

---

## Next Steps

- See [`bulk-processing.md`](./bulk-processing.md) for CSV batch processing patterns
- See [`common-errors.md`](./common-errors.md) for error handling reference
- See [`webhooks.md`](./webhooks.md) for webhook integration (future feature)
