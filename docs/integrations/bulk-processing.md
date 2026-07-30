# Batch Processing Pattern

Process large CSV files of contacts through the enrichment API with proper rate limiting, error handling, and progress tracking.

## Overview

This guide demonstrates how to:
- Read contacts from a CSV file
- Submit jobs respecting the 30 requests/min rate limit
- Poll all jobs in parallel
- Write results back to CSV
- Handle errors and resume failed batches

---

## Complete Python Implementation

```python
import csv
import time
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import json

API_TOKEN = "your-api-token-here"
BASE_URL = "https://enrich.hyrepath.io"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}


@dataclass
class Contact:
    """Input contact record."""
    email: str
    name: Optional[str] = None
    company: Optional[str] = None
    linkedin_url: Optional[str] = None


@dataclass
class EnrichmentResult:
    """Enrichment result for a contact."""
    original_email: str
    job_id: str
    status: str
    enriched_emails: List[str]
    verified_emails: List[Dict]
    social_handles: List[Dict]
    phone_numbers: List[str]
    error: Optional[str] = None


class RateLimiter:
    """Simple rate limiter for 30 requests per minute."""

    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute  # seconds between requests
        self.last_request_time = 0.0

    def wait_if_needed(self):
        """Block until enough time has passed since last request."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_interval:
            wait_time = self.min_interval - elapsed
            print(f"  ⏳ Rate limiting: waiting {wait_time:.1f}s")
            time.sleep(wait_time)

        self.last_request_time = time.time()


class BatchProcessor:
    """Batch enrichment processor with rate limiting and error handling."""

    def __init__(
        self,
        api_token: str,
        base_url: str = BASE_URL,
        rate_limit: int = 30,  # requests per minute
        tiers: List[str] = None
    ):
        self.api_token = api_token
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
        self.rate_limiter = RateLimiter(requests_per_minute=rate_limit)
        self.tiers = tiers or ["tier1", "tier2"]

    def read_contacts_from_csv(self, filepath: str) -> List[Contact]:
        """Read contacts from input CSV."""
        contacts = []

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                contact = Contact(
                    email=row.get('email', '').strip(),
                    name=row.get('name', '').strip() or None,
                    company=row.get('company', '').strip() or None,
                    linkedin_url=row.get('linkedin_url', '').strip() or None
                )

                if contact.email:  # Only add contacts with email
                    contacts.append(contact)

        print(f"✓ Loaded {len(contacts)} contacts from {filepath}")
        return contacts

    def submit_job(self, contact: Contact) -> Optional[str]:
        """
        Submit enrichment job for a contact.
        Returns job_id or None on error.
        """
        payload = {
            "email": contact.email,
            "company": contact.company,
            "linkedin_url": contact.linkedin_url,
            "requested_tiers": self.tiers
        }

        try:
            # Respect rate limit
            self.rate_limiter.wait_if_needed()

            response = requests.post(
                f"{self.base_url}/enrich",
                headers=self.headers,
                json=payload,
                timeout=30
            )

            if response.status_code == 202:
                job_id = response.json()["data"]["id"]
                return job_id
            elif response.status_code == 429:
                # Rate limit hit - wait and retry once
                retry_after = response.headers.get("Retry-After", "60")
                print(f"  ⚠ Rate limited, waiting {retry_after}s")
                time.sleep(float(retry_after))

                # Retry once
                response = requests.post(
                    f"{self.base_url}/enrich",
                    headers=self.headers,
                    json=payload,
                    timeout=30
                )

                if response.status_code == 202:
                    return response.json()["data"]["id"]

            print(f"  ✗ Error for {contact.email}: {response.status_code}")
            return None

        except Exception as e:
            print(f"  ✗ Exception for {contact.email}: {e}")
            return None

    def poll_job(self, job_id: str, timeout: int = 300) -> Dict:
        """
        Poll job until completion or timeout.
        Returns job data.
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                return {
                    "id": job_id,
                    "status": "timeout",
                    "dossier": {}
                }

            try:
                response = requests.get(
                    f"{self.base_url}/enrich/{job_id}",
                    headers=self.headers,
                    timeout=30
                )

                if response.status_code == 200:
                    job_data = response.json()["data"]
                    status = job_data["status"]

                    # Terminal states
                    if status in ["completed", "completed_no_data", "failed", "suppressed"]:
                        return job_data

                # Keep polling
                time.sleep(2)

            except Exception as e:
                print(f"  ⚠ Polling error for {job_id}: {e}")
                time.sleep(2)

    def process_batch(
        self,
        contacts: List[Contact],
        output_filepath: str,
        checkpoint_filepath: Optional[str] = None
    ) -> List[EnrichmentResult]:
        """
        Process batch of contacts with checkpointing.

        Args:
            contacts: List of contacts to enrich
            output_filepath: Path to write results CSV
            checkpoint_filepath: Path to checkpoint file (optional)

        Returns:
            List of enrichment results
        """
        results: List[EnrichmentResult] = []
        job_map: Dict[str, Contact] = {}  # job_id -> contact

        # Load checkpoint if exists
        completed_emails = set()
        if checkpoint_filepath:
            try:
                with open(checkpoint_filepath, 'r') as f:
                    checkpoint = json.load(f)
                    completed_emails = set(checkpoint.get("completed_emails", []))
                    print(f"✓ Loaded checkpoint: {len(completed_emails)} already completed")
            except FileNotFoundError:
                pass

        # Phase 1: Submit all jobs
        print(f"\n--- Phase 1: Submitting {len(contacts)} jobs ---")
        print(f"Rate limit: {self.rate_limiter.requests_per_minute} requests/min")
        print(f"Estimated time: {len(contacts) / self.rate_limiter.requests_per_minute:.1f} minutes\n")

        start_time = time.time()

        for i, contact in enumerate(contacts, 1):
            # Skip if already completed
            if contact.email in completed_emails:
                print(f"[{i}/{len(contacts)}] ⊘ Skipping {contact.email} (already completed)")
                continue

            job_id = self.submit_job(contact)

            if job_id:
                job_map[job_id] = contact
                print(f"[{i}/{len(contacts)}] ✓ {contact.email} → {job_id}")
            else:
                # Failed to submit
                result = EnrichmentResult(
                    original_email=contact.email,
                    job_id="",
                    status="submit_failed",
                    enriched_emails=[],
                    verified_emails=[],
                    social_handles=[],
                    phone_numbers=[],
                    error="Failed to submit job"
                )
                results.append(result)

        elapsed = time.time() - start_time
        print(f"\n✓ Submitted {len(job_map)} jobs in {elapsed:.1f}s")

        # Phase 2: Poll all jobs in parallel
        print(f"\n--- Phase 2: Polling {len(job_map)} jobs ---")
        print("Waiting for jobs to complete (this may take several minutes)...\n")

        poll_start = time.time()

        for i, (job_id, contact) in enumerate(job_map.items(), 1):
            print(f"[{i}/{len(job_map)}] Polling {contact.email} ({job_id})...")

            job_data = self.poll_job(job_id)
            result = self._parse_job_result(contact, job_data)
            results.append(result)

            # Update checkpoint
            if checkpoint_filepath and result.status in ["completed", "completed_no_data"]:
                completed_emails.add(contact.email)
                with open(checkpoint_filepath, 'w') as f:
                    json.dump({"completed_emails": list(completed_emails)}, f)

            print(f"  → Status: {result.status}")

        poll_elapsed = time.time() - poll_start
        print(f"\n✓ All jobs completed in {poll_elapsed:.1f}s")

        # Phase 3: Write results
        self.write_results_to_csv(results, output_filepath)

        return results

    def _parse_job_result(self, contact: Contact, job_data: Dict) -> EnrichmentResult:
        """Parse job data into EnrichmentResult."""
        dossier = job_data.get("dossier", {})
        status = job_data.get("status", "unknown")

        # Extract enriched data
        enriched_emails = dossier.get("emails", [])
        verified_emails = dossier.get("verified_emails", [])
        handles = dossier.get("handles", [])

        # Extract phone numbers from business profile if available
        phone_numbers = []
        business = dossier.get("business")
        if business and business.get("phone"):
            phone_numbers.append(business["phone"])

        return EnrichmentResult(
            original_email=contact.email,
            job_id=job_data["id"],
            status=status,
            enriched_emails=enriched_emails,
            verified_emails=verified_emails,
            social_handles=handles,
            phone_numbers=phone_numbers
        )

    def write_results_to_csv(self, results: List[EnrichmentResult], filepath: str):
        """Write enrichment results to CSV."""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'original_email',
                'job_id',
                'status',
                'enriched_emails',
                'verified_emails',
                'social_handles',
                'phone_numbers',
                'error'
            ]

            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for result in results:
                writer.writerow({
                    'original_email': result.original_email,
                    'job_id': result.job_id,
                    'status': result.status,
                    'enriched_emails': json.dumps(result.enriched_emails),
                    'verified_emails': json.dumps(result.verified_emails),
                    'social_handles': json.dumps(result.social_handles),
                    'phone_numbers': json.dumps(result.phone_numbers),
                    'error': result.error or ''
                })

        print(f"\n✓ Results written to {filepath}")

        # Print summary
        status_counts = {}
        for result in results:
            status_counts[result.status] = status_counts.get(result.status, 0) + 1

        print("\n--- Summary ---")
        for status, count in sorted(status_counts.items()):
            print(f"  {status}: {count}")


def main():
    """Example usage."""

    # Initialize processor
    processor = BatchProcessor(
        api_token=API_TOKEN,
        base_url=BASE_URL,
        rate_limit=30,  # 30 requests per minute
        tiers=["tier1", "tier2"]
    )

    # Process batch
    contacts = processor.read_contacts_from_csv("input_contacts.csv")

    results = processor.process_batch(
        contacts=contacts,
        output_filepath="enriched_results.csv",
        checkpoint_filepath="checkpoint.json"  # Resume on failure
    )

    print(f"\n✓ Processed {len(results)} contacts")


if __name__ == "__main__":
    main()
```

---

## Input CSV Format

```csv
email,name,company,linkedin_url
john.doe@example.com,John Doe,Acme Corp,https://linkedin.com/in/johndoe
jane.smith@foo.com,Jane Smith,Foo Inc,
bob@bar.io,Bob Johnson,,https://linkedin.com/in/bobjohnson
```

Required columns:
- `email` (required)

Optional columns:
- `name`
- `company`
- `linkedin_url`

---

## Output CSV Format

```csv
original_email,job_id,status,enriched_emails,verified_emails,social_handles,phone_numbers,error
john.doe@example.com,job_abc123,completed,"[""john.doe@example.com"", ""j.doe@acme.com""]","[{""value"": ""john.doe@example.com"", ""status"": ""valid""}]","[{""platform"": ""twitter"", ""username"": ""johndoe""}]","[""+1-555-0100""]",
jane.smith@foo.com,job_def456,completed_no_data,[],[],[],,"No data found"
```

---

## Progress Bar Enhancement

Add `tqdm` for visual progress tracking:

```bash
pip install tqdm
```

```python
from tqdm import tqdm

# In BatchProcessor.process_batch():

# Phase 1: Submit jobs
with tqdm(total=len(contacts), desc="Submitting jobs") as pbar:
    for i, contact in enumerate(contacts, 1):
        if contact.email in completed_emails:
            pbar.update(1)
            continue

        job_id = self.submit_job(contact)
        if job_id:
            job_map[job_id] = contact

        pbar.update(1)

# Phase 2: Poll jobs
with tqdm(total=len(job_map), desc="Polling jobs") as pbar:
    for job_id, contact in job_map.items():
        job_data = self.poll_job(job_id)
        result = self._parse_job_result(contact, job_data)
        results.append(result)

        pbar.update(1)
```

---

## Error Recovery

The checkpoint system allows resuming from failures:

```python
# First run (partial failure)
processor.process_batch(
    contacts=contacts,
    output_filepath="results.csv",
    checkpoint_filepath="checkpoint.json"
)

# Resume after fixing errors (skips already completed)
processor.process_batch(
    contacts=contacts,
    output_filepath="results.csv",
    checkpoint_filepath="checkpoint.json"
)
```

Checkpoint file format:
```json
{
  "completed_emails": [
    "john@example.com",
    "jane@example.com"
  ]
}
```

---

## Parallel Polling Optimization

For very large batches, poll jobs in parallel using `concurrent.futures`:

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def poll_jobs_parallel(self, job_map: Dict[str, Contact], max_workers: int = 10):
    """Poll multiple jobs in parallel."""
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all polling tasks
        future_to_contact = {
            executor.submit(self.poll_job, job_id): (job_id, contact)
            for job_id, contact in job_map.items()
        }

        # Process results as they complete
        with tqdm(total=len(future_to_contact), desc="Polling jobs") as pbar:
            for future in as_completed(future_to_contact):
                job_id, contact = future_to_contact[future]

                try:
                    job_data = future.result()
                    result = self._parse_job_result(contact, job_data)
                    results.append(result)
                except Exception as e:
                    print(f"Error polling {job_id}: {e}")

                pbar.update(1)

    return results
```

---

## Rate Limit Calculation

To process N contacts:

- **30 requests/min**: `N / 30` minutes to submit
- **Polling time**: Typically 30-120 seconds per job (runs in parallel)
- **Total time**: Submit time + Max polling time

Example:
- 1000 contacts
- Submit: 1000 / 30 = ~33 minutes
- Poll: ~2 minutes (all jobs polled in parallel)
- **Total: ~35 minutes**

---

## Best Practices

1. **Always use checkpointing** for large batches
2. **Set rate_limit to 25-28** (not 30) to leave margin
3. **Use progress bars** for long-running batches
4. **Validate input CSV** before processing
5. **Monitor errors** and retry failed jobs separately
6. **Consider parallel polling** for batches > 100 contacts

---

## Next Steps

- See [`python.md`](./python.md) for detailed Python client examples
- See [`nodejs.md`](./nodejs.md) for Node.js batch processing
- See [`common-errors.md`](./common-errors.md) for error handling reference
