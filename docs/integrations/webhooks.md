# Webhooks (Future Feature)

Webhook integration guide for receiving enrichment completion notifications.

> **Note:** Webhooks are not currently implemented. This document describes the planned webhook feature for future reference.

---

## Overview

Once implemented, webhooks will allow you to receive real-time notifications when enrichment jobs complete, eliminating the need for polling.

### Planned Features

- Register webhook URLs per API token
- Receive POST notifications on job completion
- Signature verification for security
- Automatic retry with exponential backoff
- Webhook delivery logs and status

---

## Planned API Endpoints

### Register Webhook

```http
POST /api/webhooks
Content-Type: application/json
Authorization: Bearer {API_TOKEN}

{
  "url": "https://your-domain.com/webhooks/enrichment",
  "events": ["job.completed", "job.failed"],
  "secret": "your-webhook-secret"
}
```

Response:
```json
{
  "success": true,
  "data": {
    "id": "webhook_abc123",
    "url": "https://your-domain.com/webhooks/enrichment",
    "events": ["job.completed", "job.failed"],
    "created_at": "2026-07-30T10:00:00Z",
    "status": "active"
  }
}
```

### List Webhooks

```http
GET /api/webhooks
Authorization: Bearer {API_TOKEN}
```

### Delete Webhook

```http
DELETE /api/webhooks/{webhook_id}
Authorization: Bearer {API_TOKEN}
```

---

## Webhook Payload

When a job completes, we'll send a POST request to your registered URL:

```json
{
  "event": "job.completed",
  "timestamp": "2026-07-30T10:15:00Z",
  "job_id": "job_abc123",
  "status": "completed",
  "data": {
    "id": "job_abc123",
    "status": "completed",
    "created_at": "2026-07-30T10:00:00Z",
    "updated_at": "2026-07-30T10:15:00Z",
    "dossier": {
      "emails": ["john.doe@example.com"],
      "verified_emails": [
        {
          "value": "john.doe@example.com",
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
      "sources": ["tier1", "tier2"]
    }
  }
}
```

---

## Signature Verification

All webhook requests will include a signature header for verification:

```http
POST /your-webhook-endpoint
Content-Type: application/json
X-Webhook-Signature: sha256=abc123...
X-Webhook-Timestamp: 1722333000

{...payload...}
```

### Python Signature Verification

```python
import hmac
import hashlib
import time

def verify_webhook_signature(
    payload: bytes,
    signature_header: str,
    timestamp_header: str,
    webhook_secret: str,
    tolerance: int = 300  # 5 minutes
) -> bool:
    """
    Verify webhook signature and timestamp.

    Args:
        payload: Raw request body (bytes)
        signature_header: Value of X-Webhook-Signature header
        timestamp_header: Value of X-Webhook-Timestamp header
        webhook_secret: Your webhook secret
        tolerance: Maximum age of webhook in seconds

    Returns:
        True if signature is valid and timestamp is recent
    """
    # Check timestamp to prevent replay attacks
    try:
        timestamp = int(timestamp_header)
        current_time = int(time.time())

        if abs(current_time - timestamp) > tolerance:
            print("❌ Webhook timestamp too old or in future")
            return False
    except (ValueError, TypeError):
        print("❌ Invalid timestamp")
        return False

    # Verify signature
    expected_signature = hmac.new(
        key=webhook_secret.encode('utf-8'),
        msg=f"{timestamp}:{payload.decode('utf-8')}".encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()

    expected_header = f"sha256={expected_signature}"

    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(signature_header, expected_header):
        print("❌ Invalid signature")
        return False

    print("✅ Webhook signature verified")
    return True
```

### Node.js Signature Verification

```typescript
import crypto from "crypto";

function verifyWebhookSignature(
  payload: string,
  signatureHeader: string,
  timestampHeader: string,
  webhookSecret: string,
  tolerance: number = 300 // 5 minutes
): boolean {
  // Check timestamp
  const timestamp = parseInt(timestampHeader, 10);
  const currentTime = Math.floor(Date.now() / 1000);

  if (Math.abs(currentTime - timestamp) > tolerance) {
    console.error("❌ Webhook timestamp too old or in future");
    return false;
  }

  // Verify signature
  const signedPayload = `${timestamp}:${payload}`;
  const expectedSignature = crypto
    .createHmac("sha256", webhookSecret)
    .update(signedPayload)
    .digest("hex");

  const expectedHeader = `sha256=${expectedSignature}`;

  // Constant-time comparison
  if (
    !crypto.timingSafeEqual(
      Buffer.from(signatureHeader),
      Buffer.from(expectedHeader)
    )
  ) {
    console.error("❌ Invalid signature");
    return false;
  }

  console.log("✅ Webhook signature verified");
  return true;
}
```

---

## Webhook Handler Examples

### Python Flask Handler

```python
from flask import Flask, request, jsonify
import json

app = Flask(__name__)

WEBHOOK_SECRET = "your-webhook-secret"

@app.route('/webhooks/enrichment', methods=['POST'])
def handle_enrichment_webhook():
    """Handle enrichment completion webhook."""

    # Get headers
    signature = request.headers.get('X-Webhook-Signature', '')
    timestamp = request.headers.get('X-Webhook-Timestamp', '')

    # Get raw payload
    payload = request.get_data()

    # Verify signature
    if not verify_webhook_signature(payload, signature, timestamp, WEBHOOK_SECRET):
        return jsonify({"error": "Invalid signature"}), 401

    # Parse payload
    data = request.json
    event = data.get('event')
    job_id = data.get('job_id')
    status = data.get('status')

    print(f"📨 Received webhook: {event} for job {job_id}")

    # Process based on event type
    if event == 'job.completed':
        handle_job_completed(data)
    elif event == 'job.failed':
        handle_job_failed(data)

    # Return 200 to acknowledge receipt
    return jsonify({"status": "received"}), 200


def handle_job_completed(data: dict):
    """Process completed job."""
    job_data = data.get('data', {})
    dossier = job_data.get('dossier', {})

    # Extract enriched data
    emails = dossier.get('emails', [])
    handles = dossier.get('handles', [])

    print(f"✅ Job completed: {len(emails)} emails, {len(handles)} social handles")

    # TODO: Store results in your database
    # store_enrichment_results(job_data)


def handle_job_failed(data: dict):
    """Process failed job."""
    job_id = data.get('job_id')
    print(f"❌ Job failed: {job_id}")

    # TODO: Handle failure (log, retry, alert, etc.)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
```

### Node.js Express Handler

```typescript
import express from "express";
import bodyParser from "body-parser";

const app = express();

// Important: Use raw body for signature verification
app.use(
  bodyParser.json({
    verify: (req, res, buf) => {
      (req as any).rawBody = buf.toString("utf8");
    },
  })
);

const WEBHOOK_SECRET = "your-webhook-secret";

app.post("/webhooks/enrichment", (req, res) => {
  const signature = req.headers["x-webhook-signature"] as string;
  const timestamp = req.headers["x-webhook-timestamp"] as string;
  const rawBody = (req as any).rawBody;

  // Verify signature
  if (!verifyWebhookSignature(rawBody, signature, timestamp, WEBHOOK_SECRET)) {
    return res.status(401).json({ error: "Invalid signature" });
  }

  // Parse payload
  const data = req.body;
  const event = data.event;
  const jobId = data.job_id;
  const status = data.status;

  console.log(`📨 Received webhook: ${event} for job ${jobId}`);

  // Process based on event type
  if (event === "job.completed") {
    handleJobCompleted(data);
  } else if (event === "job.failed") {
    handleJobFailed(data);
  }

  // Acknowledge receipt
  res.status(200).json({ status: "received" });
});

function handleJobCompleted(data: any) {
  const jobData = data.data;
  const dossier = jobData.dossier;

  const emails = dossier.emails || [];
  const handles = dossier.handles || [];

  console.log(
    `✅ Job completed: ${emails.length} emails, ${handles.length} social handles`
  );

  // TODO: Store results in your database
}

function handleJobFailed(data: any) {
  const jobId = data.job_id;
  console.log(`❌ Job failed: ${jobId}`);

  // TODO: Handle failure
}

app.listen(8080, () => {
  console.log("Webhook server listening on port 8080");
});
```

---

## Retry Logic

When implemented, our webhook system will automatically retry failed deliveries:

- **Retry attempts**: Up to 5 retries
- **Retry schedule**:
  - 1st retry: 30 seconds
  - 2nd retry: 5 minutes
  - 3rd retry: 30 minutes
  - 4th retry: 2 hours
  - 5th retry: 6 hours
- **Success criteria**: HTTP 2xx response
- **Failure handling**: After all retries exhausted, webhook delivery marked as failed

### Checking Webhook Delivery Status

```http
GET /api/webhooks/{webhook_id}/deliveries
Authorization: Bearer {API_TOKEN}
```

Response:
```json
{
  "success": true,
  "data": {
    "deliveries": [
      {
        "id": "delivery_abc123",
        "webhook_id": "webhook_xyz789",
        "job_id": "job_def456",
        "event": "job.completed",
        "status": "delivered",
        "attempts": 1,
        "last_attempt_at": "2026-07-30T10:15:01Z",
        "response_status": 200
      },
      {
        "id": "delivery_abc124",
        "webhook_id": "webhook_xyz789",
        "job_id": "job_def457",
        "event": "job.completed",
        "status": "failed",
        "attempts": 5,
        "last_attempt_at": "2026-07-30T16:15:01Z",
        "response_status": 500,
        "error": "Connection timeout"
      }
    ]
  }
}
```

---

## Best Practices

### 1. Idempotency

Handle duplicate webhook deliveries gracefully:

```python
def handle_webhook(data: dict):
    job_id = data.get('job_id')

    # Check if already processed
    if is_job_already_processed(job_id):
        print(f"⊘ Job {job_id} already processed, skipping")
        return

    # Process the webhook
    process_enrichment(data)

    # Mark as processed
    mark_job_processed(job_id)
```

### 2. Async Processing

Don't block the webhook response:

```python
from threading import Thread

@app.route('/webhooks/enrichment', methods=['POST'])
def handle_webhook():
    # Verify signature
    if not verify_signature(...):
        return jsonify({"error": "Invalid"}), 401

    data = request.json

    # Process async
    Thread(target=process_webhook_async, args=(data,)).start()

    # Return immediately
    return jsonify({"status": "received"}), 200

def process_webhook_async(data: dict):
    # Heavy processing here
    pass
```

### 3. Error Handling

Always return 2xx on success, even if processing fails internally:

```python
@app.route('/webhooks/enrichment', methods=['POST'])
def handle_webhook():
    try:
        # Verify and process
        verify_signature(...)
        process_webhook(request.json)

        return jsonify({"status": "success"}), 200

    except Exception as e:
        # Log error but still return 200 to avoid retries
        logger.error(f"Webhook processing error: {e}")

        # Return 200 to acknowledge receipt
        # (Log internally for debugging)
        return jsonify({"status": "error", "logged": True}), 200
```

### 4. Security

- **Always verify signatures** before processing
- **Use HTTPS** for your webhook endpoint
- **Validate timestamp** to prevent replay attacks
- **Store secrets securely** (environment variables, secret managers)
- **Log all webhook events** for audit trail

---

## Testing Webhooks (Future)

Once implemented, you'll be able to trigger test webhooks:

```http
POST /api/webhooks/{webhook_id}/test
Authorization: Bearer {API_TOKEN}
```

This will send a test payload to your endpoint to verify configuration.

---

## Migration from Polling to Webhooks

When webhooks become available, migrate gradually:

1. **Register webhook** while keeping polling logic
2. **Verify webhook delivery** in production
3. **Monitor delivery success rate** for 1-2 weeks
4. **Reduce polling frequency** once webhooks are stable
5. **Remove polling** after full confidence

---

## Next Steps

- See [`python.md`](./python.md) for current polling-based client
- See [`nodejs.md`](./nodejs.md) for Node.js client examples
- See [`common-errors.md`](./common-errors.md) for error handling reference

---

## Questions?

This feature is planned but not yet implemented. If you have specific webhook requirements or questions, please reach out to discuss your use case.
