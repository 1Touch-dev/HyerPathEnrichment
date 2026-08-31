"""Email test router for E2E validation (development only)."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, EmailStr

from app.core.config import get_settings
from app.services.email_service import EmailTemplate, enqueue_email

router = APIRouter(prefix="/api/email", tags=["email"])

_PROD_LIKE_ENVS = frozenset({"production", "staging"})


class TestEmailRequest(BaseModel):
    """Test email request."""

    recipient: EmailStr


class TestEmailResponse(BaseModel):
    """Test email response."""

    success: bool
    message: str
    recipient: str


def _require_dev_api_token(x_api_token: str | None) -> None:
    """Require X-API-Token matching API_TOKEN. Disabled entirely in staging/production."""
    settings = get_settings()
    if settings.app_env.strip().lower() in _PROD_LIKE_ENVS:
        raise HTTPException(status_code=404, detail="Not found")
    expected = settings.api_token.strip()
    provided = (x_api_token or "").strip()
    if not expected or not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid API token")


@router.post("/test")
async def send_test_email(
    request: TestEmailRequest,
    x_api_token: str | None = Header(default=None),
) -> TestEmailResponse:
    """Send a test email to verify email service is working.

    Development only. Requires header ``X-API-Token`` matching ``API_TOKEN``.
    Hidden (404) when ``APP_ENV`` is staging or production.
    """
    _require_dev_api_token(x_api_token)
    settings = get_settings()

    if not settings.email_enabled:
        return TestEmailResponse(
            success=False,
            message="Email service is disabled (EMAIL_ENABLED=false)",
            recipient=request.recipient,
        )

    try:
        enqueue_email(
            template=EmailTemplate.JOB_COMPLETION,
            recipient=request.recipient,
            context={
                "job_id": "test-job-12345",
                "business_name": "Test Company Inc.",
                "enriched_fields": {
                    "photo": "https://example.com/photo.jpg",
                    "email": "test@example.com",
                    "handles": {"twitter": "@testuser"},
                },
            },
        )

        return TestEmailResponse(
            success=True,
            message=f"Test email queued successfully to {request.recipient}",
            recipient=request.recipient,
        )

    except Exception as e:
        return TestEmailResponse(
            success=False,
            message=f"Failed to queue email: {e!s}",
            recipient=request.recipient,
        )
