"""Background email sending tasks."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.services.email_service import EmailTemplate, get_email_service

logger = logging.getLogger(__name__)


def send_email_task(
    template: str,
    recipient: str,
    context: dict[str, Any],
    subject: str | None = None,
) -> bool:
    """Background task to send an email.

    This runs in RQ worker, so blocking SendGrid API calls are fine.
    Each job gets its own event loop via asyncio.run.

    Args:
        template: Email template name (EmailTemplate enum value)
        recipient: Recipient email address
        context: Template context data
        subject: Optional custom subject

    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        email_service = get_email_service()
        template_enum = EmailTemplate(template)

        # Run async email service in sync worker context
        success = asyncio.run(
            email_service.send_template(
                template=template_enum,
                recipient=recipient,
                context=context,
                subject=subject,
            )
        )

        if success:
            logger.info(
                f"Email task completed successfully: {template} to {recipient}",
                extra={"template": template, "recipient": recipient},
            )
        else:
            logger.warning(
                f"Email task completed but send failed: {template} to {recipient}",
                extra={"template": template, "recipient": recipient},
            )

        return success

    except Exception as e:
        logger.exception(
            f"Email task failed: {template} to {recipient}",
            extra={"template": template, "recipient": recipient, "error": str(e)},
        )
        return False
