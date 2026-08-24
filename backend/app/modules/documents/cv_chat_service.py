"""CV-completeness chatbot service: turn-based, function-calling driven (Decision 1/2)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.llm_tools import RECORD_CV_ANSWER_TOOL, build_chat_system_prompt
from app.clients.retry import with_transient_retry
from app.core.config import get_settings
from app.domain.candidate import CVData
from app.domain.cv_completeness import compute_missing_fields, question_for_field
from app.modules.documents.models import (
    DOCUMENT_READY_STATUSES,
    CandidateDocument,
    CvChatMessage,
    CvChatSession,
)
from app.modules.documents.schemas import (
    CvChatMessageResponse,
    CvChatSessionResponse,
    CvChatTurnResponse,
)

logger = logging.getLogger(__name__)

_OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"


class CvChatService:
    """Business logic for the CV-completeness chatbot."""

    def __init__(self, db: AsyncSession, http_client: httpx.AsyncClient | None = None):
        self.db = db
        self._client = http_client or httpx.AsyncClient(timeout=30.0)
        self._settings = get_settings()

    async def start_session(self, document_id: str, user_id: UUID) -> CvChatSessionResponse:
        """Start (or resume) a chat session for a document's missing fields."""
        result = await self.db.execute(
            select(CandidateDocument).where(
                CandidateDocument.id == UUID(document_id),
                CandidateDocument.user_id == user_id,
            )
        )
        document = result.scalar_one_or_none()
        if not document:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        if document.processing_status not in DOCUMENT_READY_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Document is still processing; chat is unavailable until extraction completes",
            )

        # Resume an existing active session for this document rather than starting a duplicate.
        existing = await self.db.execute(
            select(CvChatSession).where(
                CvChatSession.document_id == document.id,
                CvChatSession.status == "active",
            )
        )
        session = existing.scalar_one_or_none()
        if session:
            return await self._session_response(session)

        cv_data = CVData(**(document.extracted_data or {})) if document.extracted_data else CVData()
        missing = compute_missing_fields(cv_data)

        session = CvChatSession(
            id=uuid4(),
            user_id=user_id,
            document_id=document.id,
            status="active" if missing else "completed",
            missing_fields_at_start=missing,
            fields_resolved=[],
            started_at=datetime.now(UTC),
            completed_at=None if missing else datetime.now(UTC),
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        if missing:
            first_question = question_for_field(missing[0])
            greeting = CvChatMessage(
                id=uuid4(),
                session_id=session.id,
                role="assistant",
                content=first_question,
                field_name=missing[0],
                created_at=datetime.now(UTC),
            )
            self.db.add(greeting)
            await self.db.commit()

        return await self._session_response(session)

    async def post_message(
        self, session_id: str, user_id: UUID, content: str
    ) -> CvChatTurnResponse:
        """Process one candidate reply: call the LLM, apply the tool call (if any), advance to next question."""
        session = await self._get_owned_session(session_id, user_id)
        if session.status != "active":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Chat session is not active"
            )

        turn_count = await self._count_messages(session.id)
        if turn_count >= self._settings.cv_chat_max_turns * 2:
            session.status = "abandoned"
            session.completed_at = datetime.now(UTC)
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Chat session reached its turn limit"
            )

        remaining = [f for f in session.missing_fields_at_start if f not in session.fields_resolved]
        if not remaining:
            session.status = "completed"
            session.completed_at = datetime.now(UTC)
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Chat session already completed"
            )

        current_field = remaining[0]
        question = question_for_field(current_field)

        user_message = CvChatMessage(
            id=uuid4(),
            session_id=session.id,
            role="user",
            content=content,
            created_at=datetime.now(UTC),
        )
        self.db.add(user_message)
        await self.db.flush()

        tool_result = await self._call_llm_with_tool(current_field, question, content)

        if tool_result is not None:
            field_name, value = tool_result
            await self._apply_field_value(session, field_name, value)
            session.fields_resolved = [*session.fields_resolved, field_name]
            await self.db.commit()

            next_remaining = [
                f for f in session.missing_fields_at_start if f not in session.fields_resolved
            ]
            if next_remaining:
                next_question = question_for_field(next_remaining[0])
                assistant_msg = CvChatMessage(
                    id=uuid4(),
                    session_id=session.id,
                    role="assistant",
                    content=f"Got it, thanks! {next_question}",
                    field_name=next_remaining[0],
                    tool_call_result={"field_name": field_name, "value": value},
                    created_at=datetime.now(UTC),
                )
            else:
                session.status = "completed"
                session.completed_at = datetime.now(UTC)
                assistant_msg = CvChatMessage(
                    id=uuid4(),
                    session_id=session.id,
                    role="assistant",
                    content="That's everything — your CV profile is now complete. Nice work!",
                    tool_call_result={"field_name": field_name, "value": value},
                    created_at=datetime.now(UTC),
                )
            self.db.add(assistant_msg)
        else:
            # No tool call: model responded conversationally without a validated answer.
            assistant_msg = CvChatMessage(
                id=uuid4(),
                session_id=session.id,
                role="assistant",
                content=f"Sorry, I didn't quite catch that. {question}",
                field_name=current_field,
                created_at=datetime.now(UTC),
            )
            self.db.add(assistant_msg)

        await self.db.commit()
        await self.db.refresh(session)
        return CvChatTurnResponse(
            session=await self._session_response(session),
            assistant_message=CvChatMessageResponse(
                id=str(assistant_msg.id),
                role=assistant_msg.role,
                content=assistant_msg.content,
                field_name=assistant_msg.field_name,
                created_at=assistant_msg.created_at,
            ),
        )

    async def _call_llm_with_tool(
        self, field_name: str, question: str, candidate_reply: str
    ) -> tuple[str, str] | None:
        """One turn-based (non-streamed) OpenAI call, per Decision 2. Returns (field_name, value) or None."""
        if not self._settings.openai_api_key:
            return None
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": build_chat_system_prompt(field_name, question)},
                {"role": "user", "content": candidate_reply},
            ],
            "tools": [RECORD_CV_ANSWER_TOOL],
            "tool_choice": "auto",
            "temperature": 0.0,
        }
        headers = {"Authorization": f"Bearer {self._settings.openai_api_key}"}
        try:
            # raise_for_status() must run *inside* the retried operation, not after
            # with_transient_retry returns — httpx doesn't raise on 4xx/5xx by itself,
            # so calling it outside would mean status-code errors (429/502/503/504)
            # never actually trigger a retry, only network-level failures would.
            async def _do_post() -> httpx.Response:
                resp = await self._client.post(_OPENAI_CHAT_URL, json=payload, headers=headers)
                resp.raise_for_status()
                return resp

            response = await with_transient_retry(_do_post)
            data = response.json()  # httpx.Response.json() is synchronous — see the §2.1 Bug 1 fix
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("CV chat LLM call failed", extra={"error": str(exc)})
            return None

        message = data.get("choices", [{}])[0].get("message", {})
        tool_calls = message.get("tool_calls") or []
        for call in tool_calls:
            if call.get("function", {}).get("name") == "record_cv_answer":
                import json as _json

                try:
                    args = _json.loads(call["function"]["arguments"])
                    field_name = str(args["field_name"])
                    values = args.get("values")
                    if isinstance(values, list) and values:
                        value = ", ".join(str(v) for v in values)
                    else:
                        value = str(args.get("value"))
                    return field_name, value
                except (KeyError, ValueError):
                    continue
        return None

    async def _apply_field_value(self, session: CvChatSession, field_name: str, value: str) -> None:
        """Write the validated answer back onto CandidateDocument.extracted_data."""
        result = await self.db.execute(
            select(CandidateDocument).where(CandidateDocument.id == session.document_id)
        )
        document = result.scalar_one()
        extracted = dict(document.extracted_data or {})

        list_fields = {"technical_skills", "desired_roles", "desired_locations"}
        if field_name in list_fields:
            extracted[field_name] = [v.strip() for v in value.split(",") if v.strip()]
        elif field_name == "total_years_experience":
            try:
                extracted[field_name] = float(value)
            except ValueError:
                extracted[field_name] = None
        else:
            extracted[field_name] = value.strip()

        document.extracted_data = extracted
        self.db.add(document)

    async def _get_owned_session(self, session_id: str, user_id: UUID) -> CvChatSession:
        result = await self.db.execute(
            select(CvChatSession).where(
                CvChatSession.id == UUID(session_id), CvChatSession.user_id == user_id
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
            )
        return session

    async def _count_messages(self, session_id: UUID) -> int:
        result = await self.db.execute(
            select(CvChatMessage).where(CvChatMessage.session_id == session_id)
        )
        return len(result.all())

    async def _session_response(self, session: CvChatSession) -> CvChatSessionResponse:
        messages_result = await self.db.execute(
            select(CvChatMessage)
            .where(CvChatMessage.session_id == session.id)
            .order_by(CvChatMessage.created_at)
        )
        messages = messages_result.scalars().all()
        return CvChatSessionResponse(
            session_id=str(session.id),
            document_id=str(session.document_id),
            status=session.status,
            missing_fields_at_start=session.missing_fields_at_start,
            fields_resolved=session.fields_resolved,
            messages=[
                CvChatMessageResponse(
                    id=str(m.id),
                    role=m.role,
                    content=m.content,
                    field_name=m.field_name,
                    created_at=m.created_at,
                )
                for m in messages
            ],
        )
