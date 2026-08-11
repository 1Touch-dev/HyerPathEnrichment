"""Business logic for outreach drafting, editing, and sending (Decision 5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.modules.documents.models import CandidateDocument
from app.modules.outreach.models import OutreachMessage
from app.modules.outreach.repository import get_owned_message, list_messages_for_user, mark_sent
from app.modules.outreach.schemas import (
    OutreachDraftRequest,
    OutreachEditRequest,
    OutreachListResponse,
    OutreachMessageResponse,
)
from app.workers.queue import QUEUE_OUTREACH, get_redis_connection

_UNSUBSCRIBE_FOOTER_TEMPLATE = (
    "\n\n---\n"
    "You're receiving this message because {sender_name} applied to or expressed interest in "
    "opportunities at {company_name} and used HyrePath to draft this note. "
    "Reply to {sender_email} directly, or let us know if you'd prefer not to receive further outreach."
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

        queue = Queue(QUEUE_OUTREACH, connection=self.redis_conn)
        rq_job = queue.enqueue(
            "app.workers.tasks.outreach.generate_outreach_draft_job",
            str(user_id),
            body.document_id,
            body.company_name,
            body.recipient_role_title,
            body.job_match_id,
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

        footer = _UNSUBSCRIBE_FOOTER_TEMPLATE.format(
            sender_name=sender_name, company_name=message.company_name, sender_email=sender_email
        )
        message.body = message.body + footer
        message = await mark_sent(self.db, message)
        return self._to_response(message)

    def _to_response(self, message: OutreachMessage) -> OutreachMessageResponse:
        return OutreachMessageResponse(
            message_id=str(message.id),
            company_name=message.company_name,
            recipient_role_title=message.recipient_role_title,
            subject=message.subject,
            body=message.body,
            status=message.status,
            sent_at=message.sent_at,
            created_at=message.created_at,
        )
