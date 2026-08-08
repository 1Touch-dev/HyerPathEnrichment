"""Email test router for E2E validation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from app.core.config import get_settings
from app.services.email_service import EmailTemplate, enqueue_email

router = APIRouter(prefix="/api/email", tags=["email"])


class TestEmailRequest(BaseModel):
    """Test email request."""

    recipient: EmailStr


class TestEmailResponse(BaseModel):
    """Test email response."""

    success: bool
    message: str
    recipient: str


def _verify_api_token(api_token: str) -> None:
    """Verify API token matches configured token."""
    settings = get_settings()
    if api_token != settings.api_token:
        raise HTTPException(status_code=401, detail="Invalid API token")


@router.post("/test")
async def send_test_email(
    request: TestEmailRequest,
    api_token: str = Depends(lambda: get_settings().api_token),
) -> TestEmailResponse:
    """Send a test email to verify email service is working.

    This endpoint sends a sample job completion email for testing purposes.
    Requires valid API_TOKEN for authentication.

    Args:
        request: Email recipient
        api_token: API token for authentication

    Returns:
        TestEmailResponse with success status and message
    """
    settings = get_settings()

    if not settings.email_enabled:
        return TestEmailResponse(
            success=False,
            message="Email service is disabled (EMAIL_ENABLED=false)",
            recipient=request.recipient,
        )

    try:
        # Enqueue test email
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
