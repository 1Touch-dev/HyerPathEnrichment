"""RQ worker task: generate an outreach draft using Perplexity company context + GPT-4o (Decision 5)."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select

import app.database.orm_registry  # noqa: F401
from app.clients.perplexity import PerplexityClient
from app.core.config import Settings, get_settings
from app.database.session import SessionLocal, engine
from app.domain.candidate import CVData
from app.infrastructure.redis import close_redis
from app.modules.documents.models import CandidateDocument
from app.modules.outreach.models import OutreachMessage

logger = logging.getLogger(__name__)

_OUTREACH_SYSTEM_PROMPT = """
You are helping a job candidate write a short, personalized outreach email to a hiring
manager. Use the candidate's background and the provided public company context. Keep it
under 150 words, professional, specific (reference at least one real detail from the
company context if provided), and end with a clear, low-friction call to action.
Return JSON: {"subject": <string>, "body": <string>}. Do not fabricate company facts
beyond what is provided in the context; if context is empty, write a more general
but still personalized-to-the-candidate message.
""".strip()


def generate_outreach_draft_job(
    user_id: str, document_id: str, company_name: str, role_title: str | None, job_match_id: str | None
) -> None:
    asyncio.run(_generate_outreach_draft_job(user_id, document_id, company_name, role_title, job_match_id))


async def _generate_outreach_draft_job(
    user_id: str, document_id: str, company_name: str, role_title: str | None, job_match_id: str | None
) -> None:
    try:
        async with SessionLocal() as session:
            doc_result = await session.execute(select(CandidateDocument).where(CandidateDocument.id == document_id))
            document = doc_result.scalar_one_or_none()
            if not document:
                raise ValueError(f"Document {document_id} not found")

            cv_data = CVData(**(document.extracted_data or {})) if document.extracted_data else CVData()

            perplexity = PerplexityClient()
            context = await perplexity.get_company_context(company_name, role_title)

            settings = get_settings()
            subject, body = await _draft_with_llm(cv_data, company_name, role_title, context["summary"], settings)

            message = OutreachMessage(
                id=uuid4(),
                user_id=UUID(user_id),
                job_match_id=UUID(job_match_id) if job_match_id else None,
                recipient_role_title=role_title,
                company_name=company_name,
                subject=subject,
                body=body,
                company_context_used=context,
                status="draft",
            )
            session.add(message)
            await session.commit()

            logger.info(
                "Outreach draft generated",
                extra={"user_id": user_id[:8], "company_name": company_name, "context_source": context["source"]},
            )
    except Exception:
        logger.error("Outreach draft generation failed", exc_info=True, extra={"user_id": user_id[:8]})
        raise
    finally:
        await close_redis()
        await engine.dispose()


async def _draft_with_llm(
    cv_data: CVData, company_name: str, role_title: str | None, company_context: str, settings: Settings
) -> tuple[str, str]:
    api_key = settings.openai_api_key.strip()
    if not api_key:
        return (
            f"Interested in opportunities at {company_name}",
            (
                f"Hello,\n\nI'm reaching out because I'm interested in {role_title or 'opportunities'} "
                f"at {company_name}. I'd welcome the chance to connect.\n\nBest regards"
            ),
        )

    candidate_summary = (
        f"Current role: {cv_data.current_role or 'N/A'}. "
        f"Skills: {', '.join(cv_data.technical_skills[:8])}. "
        f"Years of experience: {cv_data.total_years_experience or 'N/A'}."
    )
    user_content = (
        f"Candidate background: {candidate_summary}\n"
        f"Target company: {company_name}\n"
        f"Target role: {role_title or 'not specified'}\n"
        f"Public company context: {company_context or '(none available)'}"
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {"role": "system", "content": _OUTREACH_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.5,
            },
        )
        response.raise_for_status()
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        return parsed.get("subject", f"Interested in {company_name}"), parsed.get("body", "")
