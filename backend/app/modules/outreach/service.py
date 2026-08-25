"""Business logic for outreach drafting, editing, and sending (Decision 5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

from fastapi import HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.suppression import check_suppression
from app.core.config import get_settings
from app.modules.documents.models import CandidateDocument
from app.modules.outreach import linkedin_send_service
from app.modules.outreach.models import EmployerCompanyTier, OutreachMessage
from app.modules.outreach.repository import (
    get_company_tier,
    get_owned_message,
    list_messages_for_user,
    mark_sent,
    set_company_tier,
)
from app.modules.outreach.schemas import (
    OutreachDraftRequest,
    OutreachEditRequest,
    OutreachListResponse,
    OutreachMessageResponse,
    OutreachMessageType,
    OutreachStrategy,
)
from app.workers.queue import QUEUE_OUTREACH, get_redis_connection

_UNSUBSCRIBE_FOOTER_TEMPLATE = (
    "\n\n---\n"
    "You're receiving this message because {sender_name} applied to or expressed interest in "
    "opportunities at {company_name} and used HyrePath to draft this note. "
    "Reply to {sender_email} directly, or let us know if you'd prefer not to receive further "
    "outreach.\n"
    "{sender_name} — sent via HyrePath, {physical_address}"
    "\nPrivacy policy: {privacy_url}"
)


class OutreachService:
    def __init__(self, db: AsyncSession, redis_conn: Redis | None = None):
        self.db = db
        self.redis_conn = redis_conn or get_redis_connection()
        self._settings = get_settings()

    async def request_draft(self, user_id: UUID, body: OutreachDraftRequest) -> dict[str, Any]:
        """Enqueue draft generation. Returns immediately with a job reference (async, per RULE.md conventions)."""
        if not self._settings.outreach_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Outreach feature is disabled"
            )

        if body.message_type == "custom" and not (body.custom_instruction or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="custom_instruction is required when message_type='custom'",
            )

        if body.strategy == "warm_referral" and not (body.referral_context or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="referral_context is required when strategy='warm_referral'",
            )

        if body.message_type == "email" and not (body.recipient_email or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="recipient_email is required when message_type='email'",
            )

        if body.message_type == "linkedin" and not (body.recipient_linkedin_url or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="recipient_linkedin_url is required when message_type='linkedin'",
            )

        doc_result = await self.db.execute(
            select(CandidateDocument).where(
                CandidateDocument.id == UUID(body.document_id), CandidateDocument.user_id == user_id
            )
        )
        document = doc_result.scalar_one_or_none()
        if not document or document.processing_status != "completed":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="A processed CV is required"
            )

        lock_key = (
            f"outreach-draft-lock:{user_id}:{body.company_name.strip().lower()}:"
            f"{body.job_match_id or 'none'}:{body.message_type}"
        )
        lock_acquired = self.redis_conn.set(lock_key, "1", nx=True, ex=60)
        if not lock_acquired:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Draft generation already in progress for this company",
            )

        queue = Queue(QUEUE_OUTREACH, connection=self.redis_conn)
        rq_job = queue.enqueue(
            "app.workers.tasks.outreach.generate_outreach_draft_job",
            str(user_id),
            body.document_id,
            body.company_name,
            body.recipient_role_title,
            body.job_match_id,
            body.message_type,
            body.custom_instruction,
            body.strategy,
            body.referral_context,
            body.role_type,
            body.seniority,
            body.recipient_email,
            body.recipient_linkedin_url,
            job_timeout=60,
        )
        return {"rq_job_id": rq_job.id, "message": "Outreach draft generation started"}

    async def list_my_messages(self, user_id: UUID) -> OutreachListResponse:
        messages = await list_messages_for_user(self.db, user_id)
        return OutreachListResponse(messages=[self._to_response(m) for m in messages])

    async def edit_draft(
        self, user_id: UUID, message_id: str, body: OutreachEditRequest
    ) -> OutreachMessageResponse:
        message = await get_owned_message(self.db, UUID(message_id), user_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        if message.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Only drafts can be edited"
            )
        if message.message_type == "linkedin":
            subject_max = self._settings.outreach_linkedin_inmail_subject_max_chars
            body_max = self._settings.outreach_linkedin_inmail_body_max_chars
            if len(body.subject) > subject_max or len(body.body) > body_max:
                limit = subject_max if len(body.subject) > subject_max else body_max
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"LinkedIn messages are limited to {limit} characters; "
                        "please shorten before saving"
                    ),
                )
        message.subject = body.subject
        message.body = body.body
        await self.db.commit()
        await self.db.refresh(message)
        return self._to_response(message)

    async def send_message(
        self, user_id: UUID, message_id: str, sender_email: str, sender_name: str
    ) -> OutreachMessageResponse:
        """Append the mandatory disclosure footer and mark as sent (Decision 5, CAN-SPAM).

        This method does NOT actually transmit an email over SMTP in v1 — no email-sending
        infra targeting arbitrary third-party recipients exists in this repo today (verified:
        email_service.py only sends to the platform's own users via SendGrid templates, never
        to an arbitrary hiring-manager address supplied by a candidate). Marking as 'sent' here
        records the candidate's own action of copying/sending it externally themselves. Building
        real outbound send-as-the-candidate infrastructure (with its own deliverability, SPF/DKIM,
        and abuse-prevention concerns) is explicitly out of scope for this document — stated here
        so it is not silently assumed to exist.
        """
        message = await get_owned_message(self.db, UUID(message_id), user_id)
        if not message:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        if message.status != "draft":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Message already sent or discarded"
            )
        # Closes the loop flagged in OutreachMessage.admin_blocked's docstring: an admin
        # moderation decision must actually prevent sending, not just be recorded.
        if message.admin_blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This message has been blocked by an administrator and cannot be sent",
            )

        footer = ""
        if message.message_type == "linkedin":
            linkedin_profile_url = (message.recipient_linkedin_url or "").strip()
            if not linkedin_profile_url:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This draft predates recipient-LinkedIn-URL tracking; discard and redraft",
                )
            await linkedin_send_service.enqueue_send_task(
                self.db,
                outreach_message_id=message.id,
                linkedin_profile_url=linkedin_profile_url,
                action_type=(
                    "connection_request"
                    if message.strategy == "warm_referral"
                    else "direct_message"
                ),
            )
            # Status stays "draft" until a human operator completes the resulting
            # LinkedInSendTask (linkedin_send_service.complete_task) — a task being
            # created is not the same as a human having actually performed the send.
            return self._to_response(message)

        if message.message_type == "email":
            recipient_email = (message.recipient_email or "").strip()
            if not recipient_email:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="This draft predates recipient-email tracking; discard and redraft",
                )
            if await check_suppression(self.db, recipient_email):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="This recipient has opted out of outreach and cannot be messaged",
                )
            message.suppression_checked_at = datetime.now(UTC)
            footer = _UNSUBSCRIBE_FOOTER_TEMPLATE.format(
                sender_name=sender_name,
                company_name=message.company_name,
                sender_email=sender_email,
                physical_address=self._settings.outreach_physical_address,
                privacy_url=self._privacy_policy_url(),
            )
        message.body = message.body + footer
        message = await mark_sent(self.db, message)
        return self._to_response(message)

    def _privacy_policy_url(self) -> str:
        base_url = self._settings.app_public_base_url.strip()
        if base_url:
            return f"{base_url.rstrip('/')}/app/privacy"
        return "/app/privacy"

    def _to_response(self, message: OutreachMessage) -> OutreachMessageResponse:
        return OutreachMessageResponse(
            message_id=str(message.id),
            company_name=message.company_name,
            recipient_role_title=message.recipient_role_title,
            subject=message.subject,
            body=message.body,
            status=message.status,
            message_type=cast("OutreachMessageType", message.message_type),
            strategy=cast("OutreachStrategy", message.strategy),
            recipient_email=message.recipient_email,
            recipient_linkedin_url=message.recipient_linkedin_url,
            sent_at=message.sent_at,
            created_at=message.created_at,
            research_degraded=message.company_context_used.get("source") != "perplexity",
        )

    async def get_company_tier(self, company_name: str) -> EmployerCompanyTier | None:
        return await get_company_tier(self.db, company_name)

    async def set_company_tier(
        self,
        *,
        company_name: str,
        tier: str,
        set_by_user_id: UUID,
        notes: str | None,
    ) -> EmployerCompanyTier:
        return await set_company_tier(
            self.db,
            company_name=company_name,
            tier=tier,
            set_by_user_id=set_by_user_id,
            notes=notes,
        )
