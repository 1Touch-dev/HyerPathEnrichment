# Common Errors Reference

Comprehensive error handling guide for the Hyrepath Enrichment API.

---

## Error Response Format

All API errors follow this structure:

```json
{
  "success": false,
  "error": {
    "code": "error_code",
    "message": "Human-readable error message",
    "status_code": 400,
    "details": {
      "field": "additional context"
    }
  },
  "meta": null
}
```

---

## HTTP Status Codes

### 401 Unauthorized

**Cause**: Missing or invalid API token.

**Response**:
```json
{
  "success": false,
  "error": {
    "code": "unauthorized",
    "message": "Invalid or missing API token",
    "status_code": 401
  }
}
```

**How to Fix**:

1. Verify your API token is correct
2. Ensure the `Authorization` header is set:
   ```
   Authorization: Bearer YOUR_API_TOKEN
   ```
3. Check that the token hasn't expired or been revoked

**Python Example**:
```python
headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

response = requests.post(url, headers=headers, json=payload)

if response.status_code == 401:
    print("❌ Authentication failed - check your API_TOKEN")
```

**Node.js Example**:
```typescript
if (error.response?.status === 401) {
  console.error("❌ Authentication failed - check your API_TOKEN");
}
```

---

## 422 Unprocessable Entity

**Cause**: Request validation failed. Missing required fields or invalid values.

**Response Example 1**: Missing required tier inputs
```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "Tier tier1 requires at least one of: email, linkedin_url",
    "status_code": 422,
    "details": {
      "tier": "tier1",
      "required_fields": ["email", "linkedin_url"]
    }
  }
}
```

**Response Example 2**: Invalid tier value
```json
{
  "success": false,
  "error": {
    "code": "validation_error",
    "message": "Invalid requested_tiers value",
    "status_code": 422,
    "details": {
      "allowed_values": ["tier1", "tier2", "tier3", "tier4"],
      "received": ["tier5"]
    }
  }
}
```

**Common Validation Errors**:

| Tier | Required Fields (at least one) |
|------|-------------------------------|
| tier1 | `email` OR `linkedin_url` |
| tier2 | `email` OR `linkedin_url` |
| tier3 | `email` OR `linkedin_url` |
| tier4 | `business` (business name) |

**How to Fix**:

1. Check the `details` field in the error response
2. Ensure you're providing required fields for requested tiers
3. Validate tier values are in: `["tier1", "tier2", "tier3", "tier4"]`

**Python Example**:
```python
payload = {
    "email": "john@example.com",  # Required for tier1-3
    "requested_tiers": ["tier1", "tier2"]
}

response = requests.post(f"{BASE_URL}/enrich", headers=headers, json=payload)

if response.status_code == 422:
    error = response.json()["error"]
    print(f"❌ Validation error: {error['message']}")

    if error.get("details"):
        print(f"   Details: {error['details']}")
```

**Node.js Example**:
```typescript
if (error.response?.status === 422) {
  const apiError = error.response.data.error;
  console.error(`❌ Validation error: ${apiError.message}`);

  if (apiError.details) {
    console.error(`   Details:`, apiError.details);
  }
}
```

---

## 429 Too Many Requests

**Cause**: Rate limit exceeded (30 requests per minute).

**Response**:
```json
{
  "success": false,
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Please retry after 42 seconds.",
    "status_code": 429
  }
}
```

**Headers**:
```
Retry-After: 42
```

**How to Fix**:

Implement exponential backoff with jitter:

### Python Implementation

```python
import time
import random

def create_enrichment_with_backoff(
    email: str,
    max_retries: int = 5,
    base_delay: float = 2.0
) -> str:
    """
    Create enrichment job with exponential backoff on rate limits.
    """
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(
                f"{BASE_URL}/enrich",
                headers=headers,
                json={"email": email, "requested_tiers": ["tier1"]},
                timeout=30
            )

            if response.status_code == 202:
                return response.json()["data"]["id"]

            if response.status_code == 429:
                if attempt >= max_retries:
                    raise Exception("Max retries exceeded")

                # Check for Retry-After header
                retry_after = response.headers.get("Retry-After")
                if retry_after:
                    delay = float(retry_after)
                else:
                    # Exponential backoff: 2s, 4s, 8s, 16s, 32s
                    delay = base_delay * (2 ** attempt)
                    # Add jitter (±25%)
                    delay = delay * (0.75 + random.random() * 0.5)

                print(f"⏳ Rate limited. Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
                continue

            response.raise_for_status()

        except requests.exceptions.Timeout:
            if attempt >= max_retries:
                raise

            delay = base_delay * (2 ** attempt)
            print(f"⏳ Timeout. Retrying in {delay:.1f}s...")
            time.sleep(delay)

    raise Exception("Failed after all retries")
```

### Node.js Implementation

```typescript
async function createEnrichmentWithBackoff(
  email: string,
  maxRetries: number = 5,
  baseDelay: number = 2000 // milliseconds
): Promise<string> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const response = await axios.post(
        `${BASE_URL}/enrich`,
        { email, requested_tiers: ["tier1"] },
        { headers, timeout: 30000 }
      );

      return response.data.data.id;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 429) {
        if (attempt >= maxRetries) {
          throw new Error("Max retries exceeded");
        }

        // Check Retry-After header
        const retryAfter = error.response.headers["retry-after"];
        let delay: number;

        if (retryAfter) {
          delay = parseFloat(retryAfter) * 1000;
        } else {
          // Exponential backoff with jitter
          delay = baseDelay * Math.pow(2, attempt);
          delay = delay * (0.75 + Math.random() * 0.5);
        }

        console.log(
          `⏳ Rate limited. Retrying in ${(delay / 1000).toFixed(1)}s (attempt ${attempt + 1}/${maxRetries})`
        );

        await new Promise((resolve) => setTimeout(resolve, delay));
        continue;
      }

      throw error;
    }
  }

  throw new Error("Failed after all retries");
}
```

---

## 503 Service Unavailable

**Cause**: Redis or backend service temporarily unavailable.

**Response**:
```json
{
  "success": false,
  "error": {
    "code": "service_unavailable",
    "message": "Service temporarily unavailable. Please retry.",
    "status_code": 503
  }
}
```

**How to Fix**:

Implement retry logic with exponential backoff (similar to 429, but check for 503):

```python
def safe_api_call(url: str, payload: dict, max_retries: int = 3):
    """Make API call with retry on 503."""
    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 503:
                if attempt >= max_retries:
                    raise Exception("Service unavailable after retries")

                delay = 2 ** attempt  # 1s, 2s, 4s
                print(f"⏳ Service unavailable. Retrying in {delay}s...")
                time.sleep(delay)
                continue

            response.raise_for_status()
            return response.json()

        except requests.exceptions.ConnectionError:
            if attempt >= max_retries:
                raise

            delay = 2 ** attempt
            print(f"⏳ Connection error. Retrying in {delay}s...")
            time.sleep(delay)

    raise Exception("Failed after all retries")
```

---

## 400 Bad Request

**Cause**: Malformed request (invalid JSON, wrong content-type, etc.).

**Response**:
```json
{
  "success": false,
  "error": {
    "code": "bad_request",
    "message": "Invalid JSON in request body",
    "status_code": 400
  }
}
```

**How to Fix**:

1. Ensure `Content-Type: application/json` header is set
2. Validate JSON payload is properly formatted
3. Check for trailing commas or syntax errors

```python
# Correct
headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"  # Required
}

payload = {
    "email": "test@example.com",
    "requested_tiers": ["tier1"]  # Valid JSON
}

response = requests.post(url, headers=headers, json=payload)
```

---

## 404 Not Found

**Cause**: Job ID doesn't exist or has been purged.

**Response**:
```json
{
  "success": false,
  "error": {
    "code": "not_found",
    "message": "Job not found",
    "status_code": 404
  }
}
```

**How to Fix**:

1. Verify the job ID is correct
2. Check if job was created successfully
3. Be aware that old jobs may be purged after retention period

```python
try:
    response = requests.get(f"{BASE_URL}/enrich/{job_id}", headers=headers)
    response.raise_for_status()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 404:
        print(f"❌ Job {job_id} not found (may have been purged)")
```

---

## 500 Internal Server Error

**Cause**: Unexpected server error.

**Response**:
```json
{
  "success": false,
  "error": {
    "code": "internal_error",
    "message": "An internal error occurred",
    "status_code": 500
  }
}
```

**How to Fix**:

1. Retry the request (may be transient)
2. If persistent, contact support with:
   - Job ID (if available)
   - Timestamp of error
   - Request payload (without sensitive data)

---

## Job Status Errors

### `failed` Status

**Cause**: Enrichment job failed during processing.

**Response** (from `GET /enrich/{job_id}`):
```json
{
  "success": true,
  "data": {
    "id": "job_abc123",
    "status": "failed",
    "created_at": "2026-07-30T10:00:00Z",
    "updated_at": "2026-07-30T10:05:00Z",
    "dossier": {}
  }
}
```

**How to Handle**:

```python
job = get_job(job_id)

if job["status"] == "failed":
    print(f"❌ Job {job_id} failed")
    # Optionally retry with different parameters
    # Or log for manual review
```

### `suppressed` Status

**Cause**: Identifier is on the opt-out list.

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "job_abc123",
    "status": "suppressed",
    "created_at": "2026-07-30T10:00:00Z",
    "updated_at": "2026-07-30T10:00:01Z",
    "dossier": {}
  }
}
```

**How to Handle**:

```python
job = get_job(job_id)

if job["status"] == "suppressed":
    print(f"⚠ Job {job_id} suppressed (user opted out)")
    # Respect user's privacy - do not retry
    # Remove from your contact list
```

### `completed_no_data` Status

**Cause**: Job completed but no enrichment data found.

**Response**:
```json
{
  "success": true,
  "data": {
    "id": "job_abc123",
    "status": "completed_no_data",
    "created_at": "2026-07-30T10:00:00Z",
    "updated_at": "2026-07-30T10:05:00Z",
    "dossier": {
      "emails": [],
      "verified_emails": [],
      "handles": [],
      "sources": []
    }
  }
}
```

**How to Handle**:

```python
job = get_job(job_id)

if job["status"] == "completed_no_data":
    print(f"⚠ No enrichment data found for {job_id}")
    # Consider trying different identifiers (e.g., LinkedIn URL instead of email)
```

---

## Network Errors

### Connection Timeout

```python
try:
    response = requests.post(url, headers=headers, json=payload, timeout=30)
except requests.exceptions.Timeout:
    print("❌ Request timeout - check network or increase timeout")
    # Retry with exponential backoff
```

### Connection Error

```python
try:
    response = requests.post(url, headers=headers, json=payload)
except requests.exceptions.ConnectionError:
    print("❌ Connection error - check BASE_URL and network")
    # Verify BASE_URL is correct
    # Check firewall/proxy settings
```

---

## Complete Error Handling Example

### Python

```python
import requests
from requests.exceptions import HTTPError, Timeout, ConnectionError
import time

class EnrichmentAPIError(Exception):
    def __init__(self, status_code: int, code: str, message: str, details=None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(f"{status_code} {code}: {message}")


def robust_enrich(email: str, max_retries: int = 5) -> dict:
    """
    Create enrichment job with comprehensive error handling.
    """
    payload = {"email": email, "requested_tiers": ["tier1", "tier2"]}
    base_delay = 2.0

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
                return response.json()["data"]

            # Rate limit - retry with backoff
            if response.status_code == 429:
                if attempt >= max_retries:
                    raise EnrichmentAPIError(429, "rate_limit", "Max retries exceeded")

                retry_after = response.headers.get("Retry-After", base_delay * (2 ** attempt))
                wait_time = float(retry_after)
                print(f"⏳ Rate limited, waiting {wait_time}s")
                time.sleep(wait_time)
                continue

            # Service unavailable - retry with backoff
            if response.status_code == 503:
                if attempt >= max_retries:
                    raise EnrichmentAPIError(503, "service_unavailable", "Service down")

                delay = base_delay * (2 ** attempt)
                print(f"⏳ Service unavailable, waiting {delay}s")
                time.sleep(delay)
                continue

            # Other errors - parse and raise
            error_data = response.json()
            error = error_data.get("error", {})
            raise EnrichmentAPIError(
                status_code=response.status_code,
                code=error.get("code", "unknown"),
                message=error.get("message", "Unknown error"),
                details=error.get("details")
            )

        except Timeout:
            if attempt >= max_retries:
                raise EnrichmentAPIError(0, "timeout", "Request timeout")
            print(f"⏳ Timeout, retrying...")
            time.sleep(base_delay * (2 ** attempt))

        except ConnectionError:
            if attempt >= max_retries:
                raise EnrichmentAPIError(0, "connection", "Connection failed")
            print(f"⏳ Connection error, retrying...")
            time.sleep(base_delay * (2 ** attempt))

    raise EnrichmentAPIError(0, "max_retries", "Failed after all retries")


# Usage
try:
    job = robust_enrich("test@example.com")
    print(f"✓ Job created: {job['id']}")
except EnrichmentAPIError as e:
    print(f"✗ Error: {e.status_code} {e.code}")
    print(f"   {e.message}")
    if e.details:
        print(f"   Details: {e.details}")
```

---

## Quick Reference Table

| Status Code | Error Type | Retry? | Backoff? |
|-------------|------------|--------|----------|
| 400 | Bad Request | No | - |
| 401 | Unauthorized | No | - |
| 404 | Not Found | No | - |
| 422 | Validation Error | No | - |
| 429 | Rate Limit | Yes | Exponential |
| 500 | Internal Error | Yes | Exponential |
| 503 | Service Unavailable | Yes | Exponential |
| Timeout | Network Timeout | Yes | Exponential |
| Connection | Network Error | Yes | Exponential |

---

## Best Practices

1. **Always check status codes** before parsing response
2. **Implement exponential backoff** for rate limits and service errors
3. **Respect Retry-After headers** when present
4. **Log errors with context** (job ID, email, timestamp)
5. **Set reasonable timeouts** (30s for API calls, 180s for sync)
6. **Handle `suppressed` status** by removing contacts from lists
7. **Monitor error rates** and alert on spikes
8. **Don't retry 4xx errors** except 429 (rate limit)

---

## Next Steps

- See [`python.md`](./python.md) for Python client with error handling
- See [`nodejs.md`](./nodejs.md) for Node.js error handling
- See [`bulk-processing.md`](./bulk-processing.md) for batch error handling
