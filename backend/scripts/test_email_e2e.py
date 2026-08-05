#!/usr/bin/env python3
"""E2E test script for email service."""

import asyncio
import logging
import sys

from app.core.config import get_settings
from app.services.email_service import EmailTemplate, get_email_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def test_email_service() -> None:
    """Test email service end-to-end."""
    settings = get_settings()

    logger.info("=" * 60)
    logger.info("Email Service E2E Test")
    logger.info("=" * 60)

    # Check configuration
    logger.info("\n1. Checking configuration...")
    logger.info(f"   EMAIL_ENABLED: {settings.email_enabled}")
    logger.info(f"   EMAIL_TEST_MODE: {settings.email_test_mode}")
    logger.info(f"   SENDGRID_FROM_EMAIL: {settings.sendgrid_from_email}")
    logger.info(f"   SENDGRID_FROM_NAME: {settings.sendgrid_from_name}")
    logger.info(f"   SENDGRID_API_KEY configured: {'Yes' if settings.sendgrid_api_key.get_secret_value() else 'No'}")

    if not settings.email_enabled:
        logger.error("❌ EMAIL_ENABLED is False - email service is disabled")
        sys.exit(1)

    if not settings.sendgrid_api_key.get_secret_value():
        logger.error("❌ SENDGRID_API_KEY is not configured")
        sys.exit(1)

    logger.info("✅ Configuration looks good!")

    # Test email service
    logger.info("\n2. Testing email service...")
    email_service = get_email_service()

    test_recipient = "ringtones786110@gmail.com"
    logger.info(f"   Sending test email to: {test_recipient}")

    success = await email_service.send_template(
        template=EmailTemplate.JOB_COMPLETION,
        recipient=test_recipient,
        context={
            "job_id": "test-e2e-12345",
            "business_name": "E2E Test Company",
            "enriched_fields": {
                "photo": "https://example.com/test-photo.jpg",
                "email": "test@e2etest.com",
                "handles": {
                    "twitter": "@e2etest",
                    "linkedin": "https://linkedin.com/in/e2etest",
                },
                "business": {
                    "name": "E2E Test Company",
                    "website": "https://e2etest.com",
                },
            },
        },
    )

    if success:
        logger.info("✅ Email sent successfully!")
        logger.info(f"\n📧 Please check inbox at {test_recipient}")
        logger.info("   Expected subject: 'Enrichment Complete: E2E Test Company'")
    else:
        logger.error("❌ Email sending failed")
        sys.exit(1)

    logger.info("\n" + "=" * 60)
    logger.info("Test completed successfully!")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_email_service())
