"""CV-completeness chatbot service: turn-based, function-calling driven (Decision 1/2)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.clients.llm_tools import (
    _PREP_STRATEGY_SYSTEM_PROMPT,
    RECORD_CV_ANSWER_TOOL,
    build_chat_system_prompt,
    build_prep_strategy_user_prompt,
)
from app.clients.retry import with_transient_retry
from app.core.config import get_settings
from app.domain.candidate import CVData
from app.domain.cv_completeness import (
    PROGRESSIVE_FIELDS,
    compute_missing_fields,
    compute_missing_progressive_fields,
    question_for_field,
    question_for_progressive_field,
    should_generate_prep_strategy_suggestion,
)
from app.modules.brands.models import Brand
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
        # A session is only "completed" at start if BOTH required and progressive fields are
        # already resolved — required-only completeness (compute_missing_fields()) is no longer
        # sufficient on its own, since candidates who already have all required fields filled
        # in from CV extraction still get asked the progressive-profiling questions (see
        # post_message's post-required-fields branch for the same rule applied mid-session).
        missing_progressive = compute_missing_progressive_fields(cv_data)
        is_complete = not missing and not missing_progressive

        session = CvChatSession(
            id=uuid4(),
            user_id=user_id,
            document_id=document.id,
            status="completed" if is_complete else "active",
            missing_fields_at_start=missing,
            fields_resolved=[],
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC) if is_complete else None,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        if missing:
            first_field, first_question = missing[0], question_for_field(missing[0])
        elif missing_progressive:
            first_field = missing_progressive[0]
            first_question = question_for_progressive_field(missing_progressive[0])
        else:
            first_field = None
            first_question = None

        if first_question:
            greeting = CvChatMessage(
                id=uuid4(),
                session_id=session.id,
                role="assistant",
                content=first_question,
                field_name=first_field,
                created_at=datetime.now(UTC),
            )
            self.db.add(greeting)
            await self.db.commit()

        return await self._session_response(session)

    async def get_session(self, session_id: str, user_id: UUID) -> CvChatSessionResponse:
        """Fetch an owned chat session with its message history."""
        session = await self._get_owned_session(session_id, user_id)
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

        # Progressive fields (interests/learning_style/prep_timeline_weeks) reuse
        # `fields_resolved` alongside required fields rather than a separate DB column:
        # PROGRESSIVE_FIELDS and REQUIRED_FIELDS never share a field name, so one
        # resolved-field-names list can safely track both (see track-01 spec's wiring note).
        required_remaining = [
            f for f in session.missing_fields_at_start if f not in session.fields_resolved
        ]
        progressive_remaining = [f for f in PROGRESSIVE_FIELDS if f not in session.fields_resolved]
        if not required_remaining and not progressive_remaining:
            session.status = "completed"
            session.completed_at = datetime.now(UTC)
            await self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Chat session already completed"
            )

        if required_remaining:
            current_field = required_remaining[0]
            question = question_for_field(current_field)
        else:
            current_field = progressive_remaining[0]
            question = question_for_progressive_field(current_field)

        user_message = CvChatMessage(
            id=uuid4(),
            session_id=session.id,
            role="user",
            content=content,
            created_at=datetime.now(UTC),
        )
        self.db.add(user_message)
        await self.db.flush()

        tool_result = await self._call_llm_with_tool(
            current_field, question, content, session.user_id
        )

        if tool_result is not None:
            field_name, value = tool_result
            await self._apply_field_value(session, field_name, value)
            session.fields_resolved = [*session.fields_resolved, field_name]
            await self.db.commit()

            next_required_remaining = [
                f for f in session.missing_fields_at_start if f not in session.fields_resolved
            ]
            next_progressive_remaining = [
                f for f in PROGRESSIVE_FIELDS if f not in session.fields_resolved
            ]

            # If this answer was the second of the two prep-relevant progressive fields
            # (learning_style / prep_timeline_weeks), generate and queue the prep-strategy
            # suggestion as an extra assistant message — inserted *before* the next-question/
            # completion message below (see created_at ordering). This never gates completion:
            # should_generate_prep_strategy_suggestion()'s own "only if prep_strategy_suggestion
            # is None" check is the sole guard, so it fires at most once per session.
            suggestion_message: CvChatMessage | None = None
            if field_name in PROGRESSIVE_FIELDS:
                doc_result = await self.db.execute(
                    select(CandidateDocument).where(CandidateDocument.id == session.document_id)
                )
                document = doc_result.scalar_one()
                cv_data = CVData(**(document.extracted_data or {}))
                if should_generate_prep_strategy_suggestion(cv_data):
                    suggestion_text = await self._generate_prep_strategy_suggestion(cv_data)
                    if suggestion_text is not None:
                        extracted = dict(document.extracted_data or {})
                        extracted["prep_strategy_suggestion"] = suggestion_text
                        document.extracted_data = extracted
                        self.db.add(document)
                        suggestion_message = CvChatMessage(
                            id=uuid4(),
                            session_id=session.id,
                            role="assistant",
                            content=f"One more thing before we wrap up — {suggestion_text}",
                            created_at=datetime.now(UTC),
                        )
                        self.db.add(suggestion_message)

            if next_required_remaining:
                next_question = question_for_field(next_required_remaining[0])
                assistant_msg = CvChatMessage(
                    id=uuid4(),
                    session_id=session.id,
                    role="assistant",
                    content=f"Got it, thanks! {next_question}",
                    field_name=next_required_remaining[0],
                    tool_call_result={"field_name": field_name, "value": value},
                    created_at=datetime.now(UTC),
                )
            elif next_progressive_remaining:
                next_question = question_for_progressive_field(next_progressive_remaining[0])
                assistant_msg = CvChatMessage(
                    id=uuid4(),
                    session_id=session.id,
                    role="assistant",
                    content=f"Got it, thanks! {next_question}",
                    field_name=next_progressive_remaining[0],
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
        self, field_name: str, question: str, candidate_reply: str, user_id: UUID
    ) -> tuple[str, str] | None:
        """One turn-based (non-streamed) OpenAI call, per Decision 2. Returns (field_name, value) or None."""
        if not self._settings.openai_api_key:
            return None
        brand_config = await self._resolve_brand_chatbot_config(user_id)
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {
                    "role": "system",
                    "content": build_chat_system_prompt(field_name, question, brand_config),
                },
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

    async def _resolve_brand_chatbot_config(self, user_id: UUID) -> dict[str, Any] | None:
        """Loads the candidate's users.signup_brand_id and that Brand's
        chatbot_config/is_active in a single joined query. Returns None (falls back to
        default chatbot behavior) when: the user has no signup_brand_id, the referenced
        Brand row is missing/inactive, or chatbot_config itself is NULL/empty —
        all three cases must produce identical (no customization) behavior, not
        three different fallback shapes."""
        result = await self.db.execute(
            select(Brand.chatbot_config, Brand.is_active)
            .join(User, User.signup_brand_id == Brand.id)
            .where(User.id == user_id)
        )
        row = result.one_or_none()
        if row is None or not row.is_active:
            return None
        return row.chatbot_config or None

    async def _generate_prep_strategy_suggestion(self, cv_data: CVData) -> str | None:
        """One-off, free-text OpenAI call generating the interview-prep strategy suggestion.

        Same call shape as `_call_llm_with_tool` (client/settings/URL, transient-retry
        wrapper, fail-soft try/except) but with no `tools`/`tool_choice` — this is a single
        free-text generation, not a structured-extraction call. Returns the plain text
        content, or None on any HTTP/parse error (logged as a warning, never raised).
        """
        if not self._settings.openai_api_key:
            return None
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": _PREP_STRATEGY_SYSTEM_PROMPT},
                {"role": "user", "content": build_prep_strategy_user_prompt(cv_data)},
            ],
            "temperature": 0.0,
        }
        headers = {"Authorization": f"Bearer {self._settings.openai_api_key}"}
        try:

            async def _do_post() -> httpx.Response:
                resp = await self._client.post(_OPENAI_CHAT_URL, json=payload, headers=headers)
                resp.raise_for_status()
                return resp

            response = await with_transient_retry(_do_post)
            data = response.json()
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            logger.warning("CV chat prep-strategy generation failed", extra={"error": str(exc)})
            return None

        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(content, str) or not content:
            return None
        return content

    async def _apply_field_value(self, session: CvChatSession, field_name: str, value: str) -> None:
        """Write the validated answer back onto CandidateDocument.extracted_data."""
        result = await self.db.execute(
            select(CandidateDocument).where(CandidateDocument.id == session.document_id)
        )
        document = result.scalar_one()
        extracted = dict(document.extracted_data or {})

        list_fields = {"technical_skills", "desired_roles", "desired_locations", "interests"}
        if field_name in list_fields:
            extracted[field_name] = [v.strip() for v in value.split(",") if v.strip()]
        elif field_name == "total_years_experience":
            try:
                extracted[field_name] = float(value)
            except ValueError:
                extracted[field_name] = None
        elif field_name == "prep_timeline_weeks":
            # Not explicitly called out in the track spec's _apply_field_value diff, but
            # needed for correctness: CVData.prep_timeline_weeks is `int | None`, and this
            # value later round-trips through `CVData(**extracted_data)` in post_message's
            # prep-strategy-suggestion check, so it must be a real int rather than a raw
            # string like "about 4 weeks" (mirrors the total_years_experience pattern above).
            try:
                extracted[field_name] = int(float(value))
            except ValueError:
                extracted[field_name] = None
        else:
            extracted[field_name] = value.strip()

        document.extracted_data = extracted
        self.db.add(document)

    async def _get_owned_session(self, session_id: str, user_id: UUID) -> CvChatSession:
        try:
            session_uuid = UUID(session_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Chat session not found"
            ) from exc
        result = await self.db.execute(
            select(CvChatSession).where(
                CvChatSession.id == session_uuid, CvChatSession.user_id == user_id
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
