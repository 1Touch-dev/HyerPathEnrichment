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
    EMAIL_VERIFICATION = "email_verification"
    EMAIL_VERIFICATION_REMINDER = "email_verification_reminder"
    JOB_MATCH_DIGEST = "job_match_digest"
    CV_COMPLETENESS_REMINDER = "cv_completeness_reminder"
    PORTFOLIO_PUBLISHED = "portfolio_published"
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_REMINDER = "interview_reminder"
    RECRUITER_ACTION_PENDING = "recruiter_action_pending"
    ROLE_SUGGESTED = "role_suggested"


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
            EmailTemplate.EMAIL_VERIFICATION: self._render_email_verification,
            EmailTemplate.EMAIL_VERIFICATION_REMINDER: self._render_email_verification_reminder,
            EmailTemplate.JOB_MATCH_DIGEST: self._render_job_match_digest,
            EmailTemplate.CV_COMPLETENESS_REMINDER: self._render_cv_completeness_reminder,
            EmailTemplate.PORTFOLIO_PUBLISHED: self._render_portfolio_published,
            EmailTemplate.INTERVIEW_SCHEDULED: self._render_interview_scheduled,
            EmailTemplate.INTERVIEW_REMINDER: self._render_interview_reminder,
            EmailTemplate.RECRUITER_ACTION_PENDING: self._render_recruiter_action_pending,
            EmailTemplate.ROLE_SUGGESTED: self._render_role_suggested,
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

    def _render_email_verification(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render email verification email."""
        first_name = ctx.get("first_name", "")
        verification_link = ctx.get("verification_link", "")
        expiry_hours = ctx.get("expiry_hours", 24)

        subject = "Verify Your Email Address"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Welcome to Hyrepath Enrichment{", " + first_name if first_name else ""}!</h2>
            <p>Thank you for registering. Please verify your email address to activate your account.</p>

            <p style="text-align: center; margin: 30px 0;">
                <a href="{verification_link}"
                   style="background: #4CAF50; color: white; padding: 14px 28px;
                          text-decoration: none; border-radius: 4px; display: inline-block; font-size: 16px;">
                    Verify Email Address
                </a>
            </p>

            <p style="color: #666; font-size: 14px;">
                Or copy and paste this link into your browser:<br>
                <a href="{verification_link}" style="color: #4CAF50; word-break: break-all;">{verification_link}</a>
            </p>

            <p style="color: #999; font-size: 12px; margin-top: 30px;">
                This verification link expires in {expiry_hours} hours.
            </p>

            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        Welcome to Hyrepath Enrichment{", " + first_name if first_name else ""}!

        Thank you for registering. Please verify your email address to activate your account.

        Click the link below to verify your email:
        {verification_link}

        This verification link expires in {expiry_hours} hours.

        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject

    def _render_email_verification_reminder(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render email verification reminder."""
        first_name = ctx.get("first_name", "")
        verification_link = ctx.get("verification_link", "")
        expiry_hours = ctx.get("expiry_hours", 24)

        subject = "Reminder: Verify Your Email Address"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Email Verification Reminder</h2>
            <p>Hi{" " + first_name if first_name else ""},</p>
            <p>You requested a new verification link. Please verify your email address to activate your account.</p>

            <p style="text-align: center; margin: 30px 0;">
                <a href="{verification_link}"
                   style="background: #4CAF50; color: white; padding: 14px 28px;
                          text-decoration: none; border-radius: 4px; display: inline-block; font-size: 16px;">
                    Verify Email Address
                </a>
            </p>

            <p style="color: #666; font-size: 14px;">
                Or copy and paste this link into your browser:<br>
                <a href="{verification_link}" style="color: #4CAF50; word-break: break-all;">{verification_link}</a>
            </p>

            <p style="color: #999; font-size: 12px; margin-top: 30px;">
                This verification link expires in {expiry_hours} hours.
            </p>

            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        Email Verification Reminder

        Hi{" " + first_name if first_name else ""},

        You requested a new verification link. Please verify your email address to activate your account.

        Click the link below to verify your email:
        {verification_link}

        This verification link expires in {expiry_hours} hours.

        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject

    def _render_job_match_digest(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render the daily/weekly job-match digest email.

        ctx["matches"]: list of dicts with title, company, location, overall_score,
        explanation, source_url — see job_matching.py's _send_match_digest_async().
        """
        matches = ctx.get("matches", [])
        subject = f"{len(matches)} new job match{'es' if len(matches) != 1 else ''} for you"

        rows_html = "".join(
            f"""
            <tr>
              <td style="padding:12px;border-bottom:1px solid #eee;">
                <strong>{m["title"]}</strong> at {m["company"]}<br/>
                <span style="color:#666;">{m.get("location") or "Remote/Unspecified"}</span><br/>
                <span style="color:#0a7;">Match score: {m["overall_score"]}/100</span><br/>
                <p>{m.get("explanation", "")}</p>
                <a href="{m.get("source_url", "#")}">View job</a>
              </td>
            </tr>
            """
            for m in matches
        )
        html = f"<table style='width:100%;'>{rows_html}</table>"
        text = "\n\n".join(
            f"{m['title']} at {m['company']} — {m['overall_score']}/100\n{m.get('explanation', '')}"
            for m in matches
        )

        return html, text, subject

    def _render_cv_completeness_reminder(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render CV completeness reminder (nudges candidate to finish the CV chatbot)."""
        first_name = ctx.get("first_name", "")
        missing_fields = ctx.get("missing_fields", [])
        chat_link = ctx.get("chat_link", "#")

        subject = "Finish setting up your CV"

        missing_list_html = "".join(f"<li>{field}</li>" for field in missing_fields)

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Your CV is almost ready{", " + first_name if first_name else ""}!</h2>
            <p>A few details are still missing from your CV. Completing them helps us match you with better jobs.</p>
            <ul>{missing_list_html}</ul>

            <p style="text-align: center; margin: 30px 0;">
                <a href="{chat_link}"
                   style="background: #4CAF50; color: white; padding: 14px 28px;
                          text-decoration: none; border-radius: 4px; display: inline-block; font-size: 16px;">
                    Finish My CV
                </a>
            </p>

            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        Your CV is almost ready{", " + first_name if first_name else ""}!

        A few details are still missing from your CV: {", ".join(missing_fields)}

        Finish your CV: {chat_link}

        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject

    def _render_portfolio_published(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render portfolio-published confirmation with the public page link."""
        first_name = ctx.get("first_name", "")
        portfolio_url = ctx.get("portfolio_url", "#")

        subject = "Your portfolio is live!"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Your portfolio is live{", " + first_name if first_name else ""}!</h2>
            <p>Your public portfolio page has been published and is ready to share.</p>

            <p style="text-align: center; margin: 30px 0;">
                <a href="{portfolio_url}"
                   style="background: #4CAF50; color: white; padding: 14px 28px;
                          text-decoration: none; border-radius: 4px; display: inline-block; font-size: 16px;">
                    View My Portfolio
                </a>
            </p>

            <p style="color: #666; font-size: 14px;">
                Or copy and paste this link into your browser:<br>
                <a href="{portfolio_url}" style="color: #4CAF50; word-break: break-all;">{portfolio_url}</a>
            </p>

            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        Your portfolio is live{", " + first_name if first_name else ""}!

        Your public portfolio page has been published and is ready to share.

        View your portfolio: {portfolio_url}

        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject

    def _render_interview_scheduled(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render the interview-scheduled confirmation email (Module 4, Module D §8.4/§8.5).

        CTA links to both the .ics download and the prefilled Google Calendar link —
        no OAuth, just a plain link/anchor, per Module D's "no OAuth in v1" decision.
        """
        title = ctx.get("title", "your role")
        company = ctx.get("company", "the company")
        scheduled_at = ctx.get("scheduled_at", "")
        ics_download_url = ctx.get("ics_download_url", "#")
        google_calendar_link = ctx.get("google_calendar_link", "#")

        subject = f"Interview scheduled: {title} at {company}"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Your interview is scheduled!</h2>
            <p>Your interview for <strong>{title}</strong> at <strong>{company}</strong> is confirmed.</p>

            <table style="border: 1px solid #ddd; border-collapse: collapse; width: 100%; margin: 20px 0;">
                <tr style="background: #f8f9fa;">
                    <td style="padding: 12px; border: 1px solid #ddd;"><strong>When:</strong></td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{scheduled_at}</td>
                </tr>
            </table>

            <p style="text-align: center; margin: 30px 0;">
                <a href="{ics_download_url}"
                   style="background: #4CAF50; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px; display: inline-block; margin-right: 10px;">
                    Download .ics
                </a>
                <a href="{google_calendar_link}"
                   style="background: #4285F4; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    Add to Google Calendar
                </a>
            </p>

            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        Your interview is scheduled!

        Your interview for {title} at {company} is confirmed.

        When: {scheduled_at}

        Download .ics: {ics_download_url}
        Add to Google Calendar: {google_calendar_link}

        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject

    def _render_interview_reminder(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render the interview reminder email (Module 4, Module D §8.6), sent
        `interview_reminder_hours_before` (default 24h) ahead of the scheduled time —
        same CTA shape as the confirmation email above.
        """
        title = ctx.get("title", "your role")
        company = ctx.get("company", "the company")
        scheduled_at = ctx.get("scheduled_at", "")
        ics_download_url = ctx.get("ics_download_url", "#")
        google_calendar_link = ctx.get("google_calendar_link", "#")

        subject = f"Reminder: upcoming interview for {title} at {company}"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Your interview is coming up!</h2>
            <p>This is a reminder that your interview for <strong>{title}</strong> at
               <strong>{company}</strong> is coming up.</p>

            <table style="border: 1px solid #ddd; border-collapse: collapse; width: 100%; margin: 20px 0;">
                <tr style="background: #f8f9fa;">
                    <td style="padding: 12px; border: 1px solid #ddd;"><strong>When:</strong></td>
                    <td style="padding: 12px; border: 1px solid #ddd;">{scheduled_at}</td>
                </tr>
            </table>

            <p style="text-align: center; margin: 30px 0;">
                <a href="{ics_download_url}"
                   style="background: #4CAF50; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px; display: inline-block; margin-right: 10px;">
                    Download .ics
                </a>
                <a href="{google_calendar_link}"
                   style="background: #4285F4; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 4px; display: inline-block;">
                    Add to Google Calendar
                </a>
            </p>

            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        Your interview is coming up!

        This is a reminder that your interview for {title} at {company} is coming up.

        When: {scheduled_at}

        Download .ics: {ics_download_url}
        Add to Google Calendar: {google_calendar_link}

        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject

    def _render_recruiter_action_pending(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render notification that a recruiter has proposed an action (e.g. applying
        on the candidate's behalf) pending the candidate's approval.

        Uses `job_title`/`company` from ctx when available; falls back to a generic
        message otherwise (see recruiter_actions/service.py's apply_for_candidate —
        enriching this further would require extra queries not worth adding here).
        """
        first_name = ctx.get("first_name", "")
        job_title = ctx.get("job_title")
        company = ctx.get("company")

        if job_title and company:
            body = f"A recruiter has proposed applying to <strong>{job_title}</strong> at <strong>{company}</strong> on your behalf."
            text_body = (
                f"A recruiter has proposed applying to {job_title} at {company} on your behalf."
            )
        else:
            body = "A recruiter has proposed an action on your behalf."
            text_body = body

        subject = "A recruiter has proposed an action for your review"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">Action pending your review{", " + first_name if first_name else ""}</h2>
            <p>{body}</p>
            <p>Please review and approve or reject this action in your dashboard.</p>

            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        Action pending your review{", " + first_name if first_name else ""}

        {text_body}

        Please review and approve or reject this action in your dashboard.

        ---
        Hyrepath Enrichment | support@hyrepath.com
        """

        return html, text, subject

    def _render_role_suggested(self, ctx: dict[str, Any]) -> tuple[str, str, str]:
        """Render notification that a recruiter has suggested a role for the
        candidate to review (see recruiter_actions/service.py's suggest_role)."""
        first_name = ctx.get("first_name", "")
        job_title = ctx.get("job_title")
        company = ctx.get("company")

        if job_title and company:
            body = f"A recruiter has suggested <strong>{job_title}</strong> at <strong>{company}</strong> for you to review."
            text_body = f"A recruiter has suggested {job_title} at {company} for you to review."
        else:
            body = "A recruiter has suggested a role for you to review."
            text_body = body

        subject = "A recruiter has suggested a role for you"

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #2c3e50;">New role suggestion{", " + first_name if first_name else ""}</h2>
            <p>{body}</p>
            <p>Please review this suggestion in your dashboard.</p>

            <p style="color: #666; font-size: 12px; margin-top: 30px; border-top: 1px solid #eee; padding-top: 20px;">
                Hyrepath Enrichment | support@hyrepath.com
            </p>
        </body>
        </html>
        """

        text = f"""
        New role suggestion{", " + first_name if first_name else ""}

        {text_body}

        Please review this suggestion in your dashboard.

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
    from datetime import UTC, datetime, timedelta

    from redis import Redis
    from rq import Queue

    from app.workers.tasks.email_tasks import send_email_task

    settings = get_settings()
    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue("email", connection=redis_conn)

    if delay_seconds > 0:
        scheduled_time = datetime.now(UTC) + timedelta(seconds=delay_seconds)
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
