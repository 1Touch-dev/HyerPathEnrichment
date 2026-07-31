"""Centralized email sending service using SendGrid."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Any

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, ReplyTo, To

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailTemplate(str, Enum):
    """Available email templates."""

    JOB_COMPLETION = "job_completion"
    JOB_FAILED = "job_failed"
    DATA_DELETION_CONFIRMATION = "data_deletion_confirmation"
    DATA_ACCESS_VERIFICATION = "data_access_verification"
    OTP_VERIFICATION = "otp_verification"
    MARKETING_NEWSLETTER = "marketing_newsletter"


class EmailService:
    """SendGrid email service with template rendering and queue support."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: SendGridAPIClient | None = None

    @property
    def client(self) -> SendGridAPIClient | None:
        """Lazy-load SendGrid client."""
        if not self.settings.email_enabled:
            return None

        if self._client is None:
            api_key = self.settings.sendgrid_api_key.get_secret_value()
            if not api_key or api_key == "":
                logger.warning("SENDGRID_API_KEY not configured, emails will not send")
                return None
            self._client = SendGridAPIClient(api_key)

        return self._client

    async def send_template(
        self,
        template: EmailTemplate,
        recipient: str,
        context: dict[str, Any],
        *,
        subject: str | None = None,
        cc: list[str] | None = None,
        bcc: list[str] | None = None,
    ) -> bool:
        """Send a templated email.

        Args:
            template: Email template type
            recipient: Recipient email address
            context: Template context variables
            subject: Optional custom subject (uses template default if None)
            cc: Optional CC recipients
            bcc: Optional BCC recipients

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.settings.email_enabled:
            logger.info(f"Email disabled: would send {template} to {recipient}")
            return False

        if self.settings.email_test_mode:
            logger.info(f"TEST MODE: {template} email to {recipient} | Context: {context}")
            return True

        try:
            # Render template
            html_content, text_content, email_subject = self._render_template(template, context)
            final_subject = subject or email_subject

            # Build message
            message = Mail(
                from_email=Email(
                    self.settings.sendgrid_from_email, self.settings.sendgrid_from_name
                ),
                to_emails=To(recipient),
                subject=final_subject,
                html_content=Content("text/html", html_content),
                plain_text_content=Content("text/plain", text_content),
            )

            # Add reply-to
            if self.settings.sendgrid_reply_to:
                message.reply_to = ReplyTo(self.settings.sendgrid_reply_to)

            # Add CC/BCC if provided
            if cc:
                message.add_cc(cc)
            if bcc:
                message.add_bcc(bcc)

            # Send via SendGrid
            if self.client:
                response = self.client.send(message)

                if response.status_code in (200, 201, 202):
                    logger.info(
                        f"Email sent: {template} to {recipient}",
                        extra={
                            "template": template,
                            "recipient": recipient,
                            "status_code": response.status_code,
                        },
                    )
                    return True
                else:
                    logger.error(
                        f"SendGrid error: {response.status_code}",
                        extra={
                            "template": template,
                            "recipient": recipient,
                            "response_body": response.body,
                        },
                    )
                    return False

            return False

        except Exception as e:
            logger.exception(
                f"Failed to send email: {template} to {recipient}",
                extra={"template": template, "recipient": recipient, "error": str(e)},
            )
            return False

    def _render_template(
        self, template: EmailTemplate, context: dict[str, Any]
    ) -> tuple[str, str, str]:
        """Render email template to HTML, plain text, and subject.

        Returns:
            (html_content, text_content, subject)
        """
        templates = {
            EmailTemplate.JOB_COMPLETION: self._render_job_completion,
            EmailTemplate.JOB_FAILED: self._render_job_failed,
            EmailTemplate.DATA_DELETION_CONFIRMATION: self._render_data_deletion,
            EmailTemplate.DATA_ACCESS_VERIFICATION: self._render_data_access,
            EmailTemplate.OTP_VERIFICATION: self._render_otp,
            EmailTemplate.MARKETING_NEWSLETTER: self._render_newsletter,
        }

        renderer = templates.get(template)
        if not renderer:
            raise ValueError(f"Unknown template: {template}")

        return renderer(context)

    # Template renderers

    def _render_job_completion(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render job completion email."""
        job_id = ctx.get("job_id", "unknown")
        business_name = ctx.get("business_name", "N/A")
        enriched_fields = ctx.get("enriched_fields", {})

        subject = f"Enrichment Complete: {business_name}"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Enrichment Job Complete</h2>
            <p>Your enrichment job has finished successfully!</p>

            <table style="border: 1px solid #ddd; border-collapse: collapse; width: 100%; margin: 20px 0;">
                <tr style="background: #f8f9fa;">
                    <td style="padding: 12px; border: 1px solid #ddd;"><strong>Business:</strong></td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{business_name}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border: 1px solid #ddd;"><strong>Job ID:</strong></td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{job_id}</td>
                </tr>
                <tr style="background: #f8f9fa;">
                    <td style="padding: 12px; border: 1px solid #ddd;"><strong>Fields Enriched:</strong></td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{len(enriched_fields)}</td>
                </tr>
            </table>

            <p>
                <a href="https://yourdomain.com/app/jobs/{job_id}"
                   style="background: #4CAF50; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    View Results
                </a>
            </p>

            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        Enrichment Job Complete

        Your enrichment job has finished successfully!

        Business: {business_name}
        Job ID: {job_id}
        Fields Enriched: {len(enriched_fields)}

        View results: https://yourdomain.com/app/jobs/{job_id}

        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject

    def _render_job_failed(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render job failure email."""
        job_id = ctx.get("job_id", "unknown")
        error = ctx.get("error", "Unknown error")
        business_name = ctx.get("business_name", "N/A")

        subject = f"Enrichment Job Failed: {business_name}"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #d32f2f;">Enrichment Job Failed</h2>
            <p>Unfortunately, your enrichment job encountered an error.</p>

            <table style="border: 1px solid #ddd; border-collapse: collapse; width: 100%; margin: 20px 0;">
                <tr style="background: #f8f9fa;">
                    <td style="padding: 12px; border: 1px solid #ddd;"><strong>Business:</strong></td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{business_name}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; border: 1px solid #ddd;"><strong>Job ID:</strong></td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{job_id}</td>
                </tr>
                <tr style="background: #f8f9fa;">
                    <td style="padding: 12px; border: 1px solid #ddd;"><strong>Error:</strong></td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{error}</td>
                </tr>
            </table>

            <p>Please contact support if this issue persists.</p>

            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        Enrichment Job Failed

        Unfortunately, your enrichment job encountered an error.

        Business: {business_name}
        Job ID: {job_id}
        Error: {error}

        Please contact support if this issue persists.

        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject

    def _render_data_deletion(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render data deletion confirmation."""
        request_id = ctx.get("request_id", "unknown")
        subject = "Data Deletion Confirmation"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Data Deletion Confirmation</h2>
            <p>Your data deletion request has been processed successfully.</p>
            <p><strong>Request ID:</strong> {request_id}</p>
            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        Data Deletion Confirmation

        Your data deletion request has been processed successfully.

        Request ID: {request_id}

        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject

    def _render_data_access(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render data access verification."""
        verification_code = ctx.get("verification_code", "")
        subject = "Data Access Verification"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Data Access Verification</h2>
            <p>Your verification code for data access request:</p>
            <h1 style="background: #f5f5f5; padding: 20px; text-align: center;
                       letter-spacing: 8px; font-size: 32px;">{verification_code}</h1>
            <p style="color: #666;">This code expires in 1 hour.</p>
        </body>
        </html>
        """

        text = f"""
        Data Access Verification

        Your verification code is: {verification_code}

        This code expires in 1 hour.
        """

        return html, text, subject

    def _render_otp(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render OTP verification."""
        otp = ctx.get("otp", "")
        subject = "Your Verification Code"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Verification Code</h2>
            <p>Your verification code is:</p>
            <h1 style="background: #f5f5f5; padding: 20px; text-align: center;
                       letter-spacing: 8px; font-size: 32px;">{otp}</h1>
            <p style="color: #666;">This code expires in 10 minutes.</p>
        </body>
        </html>
        """

        text = f"Your verification code is: {otp}\n\nThis code expires in 10 minutes."

        return html, text, subject

    def _render_newsletter(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render marketing newsletter."""
        title = ctx.get("title", "Newsletter")
        content = ctx.get("content", "")
        unsubscribe_link = ctx.get("unsubscribe_link", "#")

        subject = title

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">{title}</h2>
            <div>{content}</div>
            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                <a href="{unsubscribe_link}">Unsubscribe</a> | Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        {title}

        {content}

        Unsubscribe: {unsubscribe_link}
        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject


# Singleton instance
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    """Get or create email service singleton."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service


def enqueue_email(
    template: EmailTemplate,
    recipient: str,
    context: dict[str, Any],
    *,
    subject: str | None = None,
    delay_seconds: int = 0,
) -> None:
    """Enqueue an email to be sent in the background.

    Args:
        template: Email template to use
        recipient: Recipient email address
        context: Template context data
        subject: Optional custom subject
        delay_seconds: Optional delay before sending
    """
    from datetime import datetime, timedelta

    from redis import Redis
    from rq import Queue

    from app.workers.tasks.email_tasks import send_email_task

    settings = get_settings()
    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue("email", connection=redis_conn)

    if delay_seconds > 0:
        scheduled_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
        queue.enqueue_at(
            scheduled_time,
            send_email_task,
            template.value,
            recipient,
            context,
            subject,
        )
    else:
        queue.enqueue(
            send_email_task,
            template.value,
            recipient,
            context,
            subject,
        )

    logger.info(f"Enqueued email: {template} to {recipient}")
