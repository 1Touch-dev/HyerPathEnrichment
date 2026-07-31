# Email Service E2E Testing Guide

This guide walks through end-to-end testing of the SendGrid email service.

## Prerequisites

1. SendGrid API Key configured
2. Docker and Docker Compose installed
3. Valid sender email verified in SendGrid

## Quick Start

### 1. Configure Environment

Create or update `.env.email` with your credentials:

```bash
EMAIL_ENABLED=true
EMAIL_TEST_MODE=false
SENDGRID_API_KEY=SG.your_api_key_here
SENDGRID_FROM_EMAIL=your-verified-sender@domain.com
SENDGRID_FROM_NAME=Hyrepath Enrichment
SENDGRID_REPLY_TO=support@domain.com
```

### 2. Test Email Service (Local Python)

Run the test script directly:

```bash
cd backend
python scripts/test_email_e2e.py
```

This will:
- Verify configuration
- Send a test email to `ringtones786110@gmail.com`
- Show success/failure status

### 3. Test via Docker Containers

#### Build and Start Services

```bash
cd backend/docker

# Build containers
docker compose build

# Start infrastructure with email worker
docker compose --env-file ../../.env.email up -d postgres redis worker-email

# Check email worker logs
docker compose logs -f worker-email
```

#### Test via API Endpoint

```bash
# Send test email via API
curl -X POST http://localhost:8000/api/email/test \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{"recipient":"ringtones786110@gmail.com"}'
```

Expected response:
```json
{
  "success": true,
  "data": {
    "success": true,
    "message": "Test email queued successfully to ringtones786110@gmail.com",
    "recipient": "ringtones786110@gmail.com"
  }
}
```

#### Monitor Email Queue

```bash
# Check Redis email queue
docker exec docker-redis-1 redis-cli LLEN queue:email

# View queued jobs
docker exec docker-redis-1 redis-cli LRANGE queue:email 0 10

# Watch worker process emails
docker compose logs -f worker-email
```

### 4. Verify Email Delivery

Check the inbox at `ringtones786110@gmail.com`:

**Expected Email:**
- **Subject:** "Enrichment Complete: E2E Test Company"
- **From:** Your configured sender email
- **Content:** HTML formatted job completion notification
- **Plain Text:** Available for email clients that don't support HTML

## Testing Different Templates

### Job Completion Email

```python
from app.services.email_service import EmailTemplate, enqueue_email

enqueue_email(
    template=EmailTemplate.JOB_COMPLETION,
    recipient="test@example.com",
    context={
        "job_id": "job-123",
        "business_name": "Acme Corp",
        "enriched_fields": {"email": "contact@acme.com"},
    },
)
```

### Job Failure Email

```python
enqueue_email(
    template=EmailTemplate.JOB_FAILED,
    recipient="test@example.com",
    context={
        "job_id": "job-456",
        "business_name": "Test Co",
        "error": "Rate limit exceeded",
    },
)
```

### OTP Verification Email

```python
enqueue_email(
    template=EmailTemplate.OTP_VERIFICATION,
    recipient="test@example.com",
    context={"otp": "123456"},
)
```

## Troubleshooting

### Email Not Sending

1. **Check configuration:**
   ```bash
   docker compose logs worker-email | grep -i "sendgrid\|email"
   ```

2. **Verify SendGrid API key:**
   - Check key is active in SendGrid dashboard
   - Verify sender email is verified

3. **Check Redis queue:**
   ```bash
   docker exec docker-redis-1 redis-cli LLEN queue:email
   ```
   If count is growing, worker might be stuck

4. **Worker health check:**
   ```bash
   docker compose ps worker-email
   # Should show "healthy" status
   ```

### Email in Spam

- Verify sender email in SendGrid
- Check SPF/DKIM records
- Use authenticated domain

### Worker Not Processing

1. **Check worker is running:**
   ```bash
   docker compose ps worker-email
   ```

2. **Check worker logs:**
   ```bash
   docker compose logs -f worker-email
   ```

3. **Restart worker:**
   ```bash
   docker compose restart worker-email
   ```

### Test Mode Not Working

Ensure `EMAIL_TEST_MODE=false` in your environment. When `true`, emails are only logged, not sent.

## Scaling Email Workers

```bash
# Scale to 3 workers for higher throughput
docker compose up -d --scale worker-email=3

# Check all workers
docker compose ps | grep worker-email
```

## Production Checklist

- [ ] SendGrid API key configured
- [ ] Sender email verified in SendGrid
- [ ] `EMAIL_ENABLED=true`
- [ ] `EMAIL_TEST_MODE=false`
- [ ] Email worker container running and healthy
- [ ] Test email delivered successfully
- [ ] Queue processing verified
- [ ] Worker logs show no errors
- [ ] Scaling tested (multiple workers)
- [ ] Failure handling tested

## Success Criteria

✅ Email worker container is healthy
✅ Test email delivered to `ringtones786110@gmail.com`
✅ Email has correct content and formatting
✅ Queue processes emails without errors
✅ Worker logs show successful sends
✅ Multiple workers can be scaled

## Next Steps

- Integrate with user authentication system
- Add user email to job metadata
- Enable job completion/failure notifications
- Add email delivery tracking
- Implement retry logic for failed sends
