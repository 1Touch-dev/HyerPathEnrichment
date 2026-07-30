# Integration Guides

Language-specific client examples and integration patterns for the Hyrepath Enrichment API.

## Quick Start

Choose your language:

- **[Python](./python.md)** - Async/sync enrichment with polling, error handling, rate limits
- **[Node.js/TypeScript](./nodejs.md)** - Promise-based client, axios interceptors, TypeScript types
- **[Batch Processing](./bulk-processing.md)** - CSV processing with rate limiting and checkpointing
- **[Common Errors](./common-errors.md)** - Error codes reference and handling strategies
- **[Webhooks](./webhooks.md)** - Future webhook integration (not yet implemented)

---

## API Overview

**Base URL**: `https://enrich.hyrepath.io`

**Authentication**: Bearer token in `Authorization` header

```bash
Authorization: Bearer YOUR_API_TOKEN
```

**Rate Limit**: 30 requests per minute

---

## Key Endpoints

### Create Async Enrichment Job

```http
POST /enrich
Content-Type: application/json
Authorization: Bearer {token}

{
  "email": "john@example.com",
  "linkedin_url": "https://linkedin.com/in/johndoe",
  "requested_tiers": ["tier1", "tier2"]
}
```

Returns `202 Accepted` with job ID. Poll `/enrich/{job_id}` for results.

### Sync Enrichment (Blocking)

```http
POST /enrich/sync
Content-Type: application/json
Authorization: Bearer {token}

{
  "email": "john@example.com",
  "requested_tiers": ["tier1"]
}
```

Returns `200 OK` with results after completion (30-120s).

### Get Job Status

```http
GET /enrich/{job_id}
Authorization: Bearer {token}
```

Returns job data with `dossier` containing enrichment results.

### List Jobs

```http
GET /enrich?limit=20&offset=0
Authorization: Bearer {token}
```

Returns paginated list of jobs.

---

## Enrichment Tiers

| Tier | Required Input | Data Returned |
|------|---------------|---------------|
| **tier1** | `email` OR `linkedin_url` | Basic profile, emails, social handles |
| **tier2** | `email` OR `linkedin_url` | Email verification, additional sources |
| **tier3** | `email` OR `linkedin_url` | Deep enrichment, coworkers, jobs |
| **tier4** | `business` (name) | Business profile, address, phone, rating |

**Example Request**:
```json
{
  "email": "john@example.com",
  "requested_tiers": ["tier1", "tier2", "tier3"]
}
```

---

## Response Format

### Success Response

```json
{
  "success": true,
  "data": {
    "id": "job_abc123",
    "status": "completed",
    "created_at": "2026-07-30T10:00:00Z",
    "updated_at": "2026-07-30T10:05:00Z",
    "dossier": {
      "emails": ["john@example.com", "john.doe@company.com"],
      "verified_emails": [
        {
          "value": "john@example.com",
          "status": "valid",
          "confidence": 0.95,
          "source": "tier1"
        }
      ],
      "handles": [
        {
          "platform": "twitter",
          "username": "johndoe",
          "profile_url": "https://twitter.com/johndoe",
          "confidence": 0.9
        }
      ],
      "photo": {
        "source": "linkedin",
        "asset_url": "https://...",
        "captured_at": "2026-07-30T10:05:00Z",
        "confidence": 0.95
      },
      "jobs": [
        {
          "title": "Software Engineer",
          "company": "Acme Corp",
          "location": "San Francisco, CA",
          "remote": true,
          "source": "tier3"
        }
      ],
      "coworkers": ["jane@acme.com", "bob@acme.com"],
      "sources": ["tier1", "tier2", "tier3"]
    }
  }
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Rate limit exceeded. Please retry after 42 seconds.",
    "status_code": 429,
    "details": {}
  }
}
```

---

## Job Statuses

| Status | Description |
|--------|-------------|
| `queued` | Job submitted, waiting to start |
| `running` | Currently processing |
| `completed` | Successfully completed with data |
| `completed_no_data` | Completed but no data found |
| `failed` | Processing failed |
| `suppressed` | User opted out |
| `purged` | Old job data purged |

---

## Common Error Codes

| Status | Code | Description | Retry? |
|--------|------|-------------|--------|
| 401 | `unauthorized` | Invalid/missing API token | No |
| 422 | `validation_error` | Invalid request payload | No |
| 429 | `rate_limit_exceeded` | Too many requests | Yes, with backoff |
| 503 | `service_unavailable` | Service temporarily down | Yes, with backoff |

See [common-errors.md](./common-errors.md) for complete reference.

---

## Quick Examples

### Python

```python
import requests
import time

API_TOKEN = "your-api-token"
BASE_URL = "https://enrich.hyrepath.io"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Create job
response = requests.post(
    f"{BASE_URL}/enrich",
    headers=headers,
    json={"email": "john@example.com", "requested_tiers": ["tier1"]}
)
job_id = response.json()["data"]["id"]

# Poll until complete
while True:
    response = requests.get(f"{BASE_URL}/enrich/{job_id}", headers=headers)
    job = response.json()["data"]

    if job["status"] in ["completed", "failed"]:
        break

    time.sleep(2)

print(f"Emails: {job['dossier'].get('emails', [])}")
```

### Node.js

```typescript
import axios from "axios";

const API_TOKEN = "your-api-token";
const BASE_URL = "https://enrich.hyrepath.io";

const headers = {
  Authorization: `Bearer ${API_TOKEN}`,
  "Content-Type": "application/json",
};

// Create job
const response = await axios.post(
  `${BASE_URL}/enrich`,
  { email: "john@example.com", requested_tiers: ["tier1"] },
  { headers }
);

const jobId = response.data.data.id;

// Poll until complete
let job;
while (true) {
  const pollResponse = await axios.get(
    `${BASE_URL}/enrich/${jobId}`,
    { headers }
  );

  job = pollResponse.data.data;

  if (["completed", "failed"].includes(job.status)) {
    break;
  }

  await new Promise((resolve) => setTimeout(resolve, 2000));
}

console.log(`Emails: ${job.dossier.emails || []}`);
```

### cURL

```bash
# Create job
curl -X POST https://enrich.hyrepath.io/enrich \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "requested_tiers": ["tier1"]
  }'

# Get job
curl -X GET https://enrich.hyrepath.io/enrich/JOB_ID \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## Best Practices

1. **Rate Limiting**: Stay under 30 requests/min, implement exponential backoff
2. **Polling**: Use 2-5 second intervals, timeout after 5 minutes
3. **Error Handling**: Always handle 429, 503, and network errors with retries
4. **Async vs Sync**: Use async for bulk processing, sync for single requests
5. **Batch Processing**: Use checkpointing for large CSV files
6. **Security**: Store API tokens in environment variables, never commit to code
7. **Opt-Out**: Respect `suppressed` status, remove contacts from lists
8. **Monitoring**: Log all API calls, track error rates

---

## OpenAPI Specification

The complete API specification is available at:

```
GET https://enrich.hyrepath.io/openapi.json
```

Or in the repository:

```
frontend/openapi/openapi.json
```

Use tools like [openapi-generator](https://openapi-generator.tech/) to generate clients.

---

## Support

- **Documentation**: See individual language guides for detailed examples
- **API Explorer**: Visit `https://enrich.hyrepath.io/docs` for interactive API testing
- **Rate Limits**: Contact support for custom rate limits

---

## Next Steps

1. Choose your language: [Python](./python.md) | [Node.js](./nodejs.md)
2. Review [common errors](./common-errors.md) for error handling
3. For batch processing, see [bulk-processing.md](./bulk-processing.md)
4. Check out [webhooks.md](./webhooks.md) for future webhook support
