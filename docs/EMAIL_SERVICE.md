# Email Service Documentation

## Overview

The email service provides a centralized, queue-based email sending system using SendGrid. It supports multiple email templates (job completion, failures, OTP, compliance notifications) with HTML and plain text formats.

## Architecture

```
┌─────────────┐     Enqueue      ┌──────────────┐
│ Application │ ───────────────> │ Redis Queue  │
│   Code      │    (email job)   │   (email)    │
└─────────────┘                  └──────────────┘
                                        │
                                        │ Poll
                                        ▼
                                 ┌──────────────┐
                                 │ Email Worker │
                                 │  Container   │
                                 └──────────────┘
                                        │
                                        │ Send
                                        ▼
                                 ┌──────────────┐
                                 │  SendGrid    │
                                 │     API      │
                                 └──────────────┘
```

### Components

1. **Email Service** (`backend/app/services/email_service.py`)
   - Core email sending logic
   - Template rendering (HTML + plain text)
   - SendGrid API integration
   - Queue enqueueing helper

2. **Email Worker Tasks** (`backend/app/workers/tasks/email_tasks.py`)
   - RQ background task handler
   - Async-to-sync bridge for worker execution

3. **Email Worker Container** (Docker Compose)
   - Dedicated worker process for email queue
   - Polls `redis://redis:6379/0` queue `email`
   - Horizontally scalable

4. **Test Endpoint** (`backend/app/modules/email/router.py`)
   - `POST /api/email/test` for E2E validation
   - Requires API token authentication

## Configuration

### Environment Variables

```bash
# Enable/disable email service
EMAIL_ENABLED=true

# Test mode (logs instead of sending)
EMAIL_TEST_MODE=false

# SendGrid API credentials
SENDGRID_API_KEY=SG.your_api_key_here
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
SENDGRID_FROM_NAME=Hyrepath Enrichment
SENDGRID_REPLY_TO=support@yourdomain.com
```

### Settings Class

All email settings are defined in `backend/app/core/config.py`:

```python
class Settings(BaseSettings):
    sendgrid_api_key: SecretStr
    sendgrid_from_email: str
    sendgrid_from_name: str
    sendgrid_reply_to: str
    email_enabled: bool
    email_test_mode: bool
```

## Usage

### Sending Emails

#### Async (Direct Send)

```python
from app.services.email_service import EmailTemplate, get_email_service

email_service = get_email_service()

success = await email_service.send_template(
    template=EmailTemplate.JOB_COMPLETION,
    recipient="user@example.com",
    context={
        "job_id": "job-123",
        "business_name": "Acme Corp",
        "enriched_fields": {...},
    },
)
```

#### Background (Queue)

```python
from app.services.email_service import EmailTemplate, enqueue_email

# Enqueue for background sending
enqueue_email(
    template=EmailTemplate.JOB_COMPLETION,
    recipient="user@example.com",
    context={
        "job_id": "job-123",
        "business_name": "Acme Corp",
        "enriched_fields": {...},
    },
)
```

#### Delayed Sending

```python
# Send after 60 seconds
enqueue_email(
    template=EmailTemplate.OTP_VERIFICATION,
    recipient="user@example.com",
    context={"otp": "123456"},
    delay_seconds=60,
)
```

## Available Templates

### 1. Job Completion

**Template:** `EmailTemplate.JOB_COMPLETION`

**Context:**
- `job_id` (str): Enrichment job ID
- `business_name` (str): Business or person name
- `enriched_fields` (dict): Enriched data fields

**Subject:** "Enrichment Complete: {business_name}"

**Use case:** Notify users when enrichment jobs finish successfully

### 2. Job Failure

**Template:** `EmailTemplate.JOB_FAILED`

**Context:**
- `job_id` (str): Job ID
- `business_name` (str): Business or person name
- `error` (str): Error message

**Subject:** "Enrichment Job Failed: {business_name}"

**Use case:** Alert users when jobs fail

### 3. OTP Verification

**Template:** `EmailTemplate.OTP_VERIFICATION`

**Context:**
- `otp` (str): One-time password code

**Subject:** "Your Verification Code"

**Use case:** Send OTP for authentication

### 4. Data Deletion Confirmation

**Template:** `EmailTemplate.DATA_DELETION_CONFIRMATION`

**Context:**
- `request_id` (str): Deletion request ID

**Subject:** "Data Deletion Confirmation"

**Use case:** GDPR compliance - confirm data deletion

### 5. Data Access Verification

**Template:** `EmailTemplate.DATA_ACCESS_VERIFICATION`

**Context:**
- `verification_code` (str): Verification code

**Subject:** "Data Access Verification"

**Use case:** GDPR compliance - verify data access requests

### 6. Marketing Newsletter

**Template:** `EmailTemplate.MARKETING_NEWSLETTER`

**Context:**
- `title` (str): Newsletter title
- `content` (str): Newsletter content (HTML)
- `unsubscribe_link` (str): Unsubscribe URL

**Subject:** {title}

**Use case:** Marketing communications with unsubscribe link

## Adding New Templates

1. **Add enum value** in `EmailTemplate`:
   ```python
   class EmailTemplate(str, Enum):
       NEW_TEMPLATE = "new_template"
   ```

2. **Create renderer method**:
   ```python
   def _render_new_template(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
       """Render new template email."""
       # Extract context
       value = ctx.get("key", "default")

       subject = f"Subject: {value}"

       html = f"""
       <html>
       <body style="font-family: Arial, sans-serif;">
           <h2>{value}</h2>
           <!-- Your HTML template -->
       </body>
       </html>
       """

       text = f"Plain text version: {value}"

       return html, text, subject
   ```

3. **Register in `_render_template`**:
   ```python
   templates = {
       # ... existing templates ...
       EmailTemplate.NEW_TEMPLATE: self._render_new_template,
   }
   ```

## Testing

### Local Testing

```bash
cd backend
python scripts/test_email_e2e.py
```

### API Testing

```bash
curl -X POST http://localhost:8000/api/email/test \
  -H "Authorization: Bearer your_api_token" \
  -H "Content-Type: application/json" \
  -d '{"recipient":"test@example.com"}'
```

### Docker Testing

See [`docs/EMAIL_SERVICE_TESTING.md`](EMAIL_SERVICE_TESTING.md) for comprehensive testing guide.

## Monitoring

### Queue Status

```bash
# Check email queue length
docker exec docker-redis-1 redis-cli LLEN queue:email

# View queued jobs
docker exec docker-redis-1 redis-cli LRANGE queue:email 0 10

# Monitor queue in real-time
docker exec docker-redis-1 redis-cli --scan --pattern queue:email*
```

### Worker Logs

```bash
# View email worker logs
docker compose logs -f worker-email

# Check worker status
docker compose ps worker-email

# Worker health
docker inspect docker-worker-email-1 --format='{{.State.Health.Status}}'
```

### Metrics

Email sends are logged with structured logging:

```python
logger.info(
    "Email sent: job_completion to user@example.com",
    extra={
        "template": "job_completion",
        "recipient": "user@example.com",
        "status_code": 202,
    }
)
```

## Scaling

### Horizontal Scaling

```bash
# Scale to 3 email workers
docker compose up -d --scale worker-email=3

# Verify all workers are running
docker compose ps | grep worker-email
```

**Benefits:**
- Higher email throughput
- Fault tolerance (if one worker fails, others continue)
- No port conflicts (bridge networking)

### Performance Tuning

- **Queue size:** Monitor with `LLEN queue:email`
- **Worker count:** Scale based on queue backlog
- **SendGrid rate limits:** Check your plan limits
- **Redis connection pool:** Increase if needed

## Error Handling

### Automatic Retry

RQ automatically retries failed jobs:
- Default: 3 retries with exponential backoff
- Configure in `enqueue_email()` if needed

### Failed Job Handling

```bash
# Check failed jobs
docker exec docker-redis-1 redis-cli LLEN queue:email:failed

# View failed job details
docker exec docker-redis-1 redis-cli LRANGE queue:email:failed 0 10
```

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `401 Unauthorized` | Invalid API key | Check `SENDGRID_API_KEY` |
| `403 Forbidden` | Sender not verified | Verify email in SendGrid |
| `Connection refused` | Redis unavailable | Check Redis container |
| `Email disabled` | `EMAIL_ENABLED=false` | Set to `true` |

## Security

### API Key Protection

- API key stored as `SecretStr` (never logged)
- Use environment variables, not hardcoded
- Rotate keys regularly in SendGrid dashboard

### Email Validation

- Recipients validated as proper email format
- Use `EmailStr` Pydantic type for validation
- Sanitize context data to prevent injection

### Authentication

Test endpoint requires API token:
```bash
curl -H "Authorization: Bearer ${API_TOKEN}" ...
```

## Best Practices

### 1. Always Use Queue for User-Facing Emails

❌ **Bad** (blocks request):
```python
await email_service.send_template(...)
```

✅ **Good** (non-blocking):
```python
enqueue_email(...)
```

### 2. Handle Failures Gracefully

```python
try:
    enqueue_email(...)
except Exception as e:
    logger.warning("Email queuing failed", exc_info=True)
    # Don't fail the main operation
```

### 3. Test Mode in Development

```bash
# Development
EMAIL_TEST_MODE=true

# Production
EMAIL_TEST_MODE=false
```

### 4. Structured Logging

```python
logger.info(
    "Email sent",
    extra={
        "template": template.value,
        "recipient": recipient,
        "job_id": job_id,
    }
)
```

### 5. Sender Verification

Before production:
1. Verify sender email in SendGrid
2. Set up SPF/DKIM records
3. Use authenticated domain

## Integration Points

### Job Completion

Emails are automatically sent on job completion (currently disabled until user system is implemented):

See `backend/app/workers/tasks/enrichment.py` for integration example.

### Future Integrations

- User registration/authentication
- Password reset
- Account verification
- Compliance notifications (GDPR)
- Marketing campaigns

## Troubleshooting

### Email Not Sending

1. Check `EMAIL_ENABLED=true`
2. Check `EMAIL_TEST_MODE=false`
3. Verify SendGrid API key
4. Check worker logs: `docker compose logs worker-email`
5. Check queue: `redis-cli LLEN queue:email`

### Emails Going to Spam

1. Verify sender email in SendGrid
2. Set up SPF/DKIM/DMARC records
3. Use authenticated domain
4. Avoid spam trigger words

### Worker Not Processing

1. Check worker is running: `docker compose ps worker-email`
2. Check Redis connection
3. Restart worker: `docker compose restart worker-email`

## Production Checklist

- [ ] SendGrid API key configured
- [ ] Sender email verified
- [ ] `EMAIL_ENABLED=true`
- [ ] `EMAIL_TEST_MODE=false`
- [ ] Worker container healthy
- [ ] Test email delivered
- [ ] Queue processing verified
- [ ] Error handling tested
- [ ] Scaling tested
- [ ] Monitoring configured
- [ ] SPF/DKIM records set up

## References

- [SendGrid API Documentation](https://docs.sendgrid.com/api-reference)
- [Email Service Testing Guide](EMAIL_SERVICE_TESTING.md)
- [Docker Networking](../backend/docker/NETWORKING.md)
- [RQ Documentation](https://python-rq.org/)
