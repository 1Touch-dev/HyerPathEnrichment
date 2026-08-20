"""RQ worker task: generate an outreach draft using Perplexity company context + GPT-4o (Decision 5)."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID, uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.database.orm_registry  # noqa: F401
from app.clients.perplexity import PerplexityClient
from app.clients.retry import with_transient_retry
from app.core.config import Settings, get_settings
from app.database.session import SessionLocal, engine
from app.domain.candidate import CVData
from app.infrastructure.redis import close_redis
from app.modules.documents.models import CandidateDocument

# JobMatch/JobPosting are owned by the job_matching module — imported here
# read-only, never redefined, same cross-module convention job_swipe/repository.py
# already uses for its own read-only access to Module 1's tables.
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.outreach.models import OutreachMessage
from app.observability.outreach_metrics import outreach_drafts_by_type_total

logger = logging.getLogger(__name__)

_EMAIL_SYSTEM_PROMPT = """
You are helping a job candidate write a short, personalized outreach email to a hiring
manager. Use the candidate's background, the job description excerpt (if provided), and
the provided public company context. The email's core purpose is a tailored value
proposition: explain specifically why the candidate would be valuable to this company,
connecting their real skills/experience to the company's actual needs (from the job
description or company context) — not a generic "I'm interested" note. Keep it under 150
words, professional, specific (reference at least one real detail from the job description
or company context if provided), and end with a clear, low-friction call to action.
Return JSON: {"subject": <string>, "body": <string>}. Do not fabricate company facts
beyond what is provided in the context; if context is empty, write a more general
but still personalized-to-the-candidate message.
""".strip()

_LINKEDIN_SYSTEM_PROMPT = """
You are helping a job candidate write a short LinkedIn message to a hiring manager or
recruiter. LinkedIn InMail messages are capped at 200 characters for the subject line and
1,900 characters for the body — write well within these limits (aim for under 150 words in
the body; LinkedIn's own guidance is that shorter InMails perform better). Do not include an
email-style signature block or a formal letter salutation ("Dear ..."); LinkedIn messages
read as brief, direct, professional notes. Reference at least one real detail from the job
description or company context if provided. End with a clear, low-friction call to action
(e.g., suggesting a short call). Return JSON: {"subject": <string, <=200 chars>, "body":
<string, <=1900 chars>}.
""".strip()

_GENERIC_SYSTEM_PROMPT = """
You are helping a job candidate write a short, informal outreach message (e.g., a text
message or DM to a personal contact/referral, not a formal email to a stranger). Keep it
brief (under 100 words), warm, and direct — this is going to someone the candidate likely
already knows or has a warm introduction to, not a cold outreach. No email-style subject
line is needed; return JSON: {"subject": <string, can be empty>, "body": <string>}.
""".strip()

_CUSTOM_INSTRUCTION_PREFIX = """
Additional instructions from the candidate for this specific message (follow these in
addition to, not instead of, the grounding in the candidate's real background, the job
description, and company context provided below):
""".strip()

_SYSTEM_PROMPTS_BY_TYPE = {
    "email": _EMAIL_SYSTEM_PROMPT,
    "linkedin": _LINKEDIN_SYSTEM_PROMPT,
    "generic": _GENERIC_SYSTEM_PROMPT,
    "custom": _EMAIL_SYSTEM_PROMPT,
}


def generate_outreach_draft_job(
    user_id: str,
    document_id: str,
    company_name: str,
    role_title: str | None,
    job_match_id: str | None,
    message_type: str = "email",
    custom_instruction: str | None = None,
) -> None:
    asyncio.run(
        _generate_outreach_draft_job(
            user_id,
            document_id,
            company_name,
            role_title,
            job_match_id,
            message_type,
            custom_instruction,
        )
    )


async def _generate_outreach_draft_job(
    user_id: str,
    document_id: str,
    company_name: str,
    role_title: str | None,
    job_match_id: str | None,
    message_type: str = "email",
    custom_instruction: str | None = None,
) -> None:
    try:
        async with SessionLocal() as session:
            doc_result = await session.execute(
                select(CandidateDocument).where(CandidateDocument.id == UUID(document_id))
            )
            document = doc_result.scalar_one_or_none()
            if not document:
                raise ValueError(f"Document {document_id} not found")

            cv_data = (
                CVData(**(document.extracted_data or {})) if document.extracted_data else CVData()
            )

            job_description = await _get_job_description(session, job_match_id, UUID(user_id))

            perplexity = PerplexityClient()
            context = await perplexity.get_company_context(company_name, role_title)

            settings = get_settings()
            subject, body = await _draft_with_llm(
                cv_data,
                company_name,
                role_title,
                context["summary"],
                job_description,
                settings,
                message_type,
                custom_instruction,
            )

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
                message_type=message_type,
                custom_instruction=custom_instruction,
            )
            session.add(message)
            await session.commit()

            outreach_drafts_by_type_total.labels(message_type=message_type).inc()

            logger.info(
                "Outreach draft generated",
                extra={
                    "user_id": user_id[:8],
                    "company_name": company_name,
                    "context_source": context["source"],
                    "message_type": message_type,
                },
            )
    except Exception:
        logger.error(
            "Outreach draft generation failed", exc_info=True, extra={"user_id": user_id[:8]}
        )
        raise
    finally:
        await close_redis()
        await engine.dispose()


async def _get_job_description(
    session: AsyncSession, job_match_id: str | None, user_id: UUID
) -> str | None:
    """Job posting description text for the match this draft is about, if any.

    `job_match_id` is only ever stored on `OutreachMessage` for audit purposes today
    (§6.6's design notes) — this is what actually grounds the draft in the real job
    posting's description, per the original feature spec's "pulls context from: job
    description" requirement. Read-only cross-module access to Module 1's tables,
    same convention `job_swipe/repository.py` already uses.
    """
    if not job_match_id:
        return None
    match_result = await session.execute(
        select(JobMatch).where(JobMatch.id == UUID(job_match_id), JobMatch.user_id == user_id)
    )
    match = match_result.scalar_one_or_none()
    if not match:
        return None
    if match.job_posting_id is None:
        # Manual entry (Module F, §10.6) — no JobPosting row to look up at all, and
        # therefore no description_raw to draft outreach from. Returning early here
        # avoids an unnecessary query and keeps the "no description available"
        # behavior identical to the existing not-found/no-description-raw cases below.
        return None
    posting_result = await session.execute(
        select(JobPosting).where(JobPosting.id == match.job_posting_id)
    )
    posting = posting_result.scalar_one_or_none()
    if not posting or not posting.description_raw:
        return None
    return posting.description_raw[:1500]


async def _draft_with_llm(
    cv_data: CVData,
    company_name: str,
    role_title: str | None,
    company_context: str,
    job_description: str | None,
    settings: Settings,
    message_type: str = "email",
    custom_instruction: str | None = None,
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
        f"Job description excerpt: {job_description or '(none available)'}\n"
        f"Public company context: {company_context or '(none available)'}"
    )
    if message_type == "custom" and custom_instruction:
        user_content = f"{user_content}\n\n{_CUSTOM_INSTRUCTION_PREFIX}\n{custom_instruction}"

    system_prompt = _SYSTEM_PROMPTS_BY_TYPE.get(message_type, _EMAIL_SYSTEM_PROMPT)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # raise_for_status() must run *inside* the retried operation, not after
        # with_transient_retry returns — httpx doesn't raise on 4xx/5xx by itself,
        # so calling it outside would mean status-code errors (429/502/503/504)
        # never actually trigger a retry, only network-level failures would.
        async def _do_post() -> httpx.Response:
            resp = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.5,
                },
            )
            resp.raise_for_status()
            return resp

        response = await with_transient_retry(_do_post)
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        subject = parsed.get("subject", f"Interested in {company_name}")
        body = parsed.get("body", "")

        if message_type == "linkedin":
            if len(subject) > settings.outreach_linkedin_inmail_subject_max_chars:
                subject = (
                    subject[: settings.outreach_linkedin_inmail_subject_max_chars - 1].rstrip()
                    + "…"
                )
            if len(body) > settings.outreach_linkedin_inmail_body_max_chars:
                body = body[: settings.outreach_linkedin_inmail_body_max_chars - 1].rstrip() + "…"
            # Truncation is a defensive backstop, not the primary control — the system
            # prompt above already instructs the model to stay within limits; this catches
            # the cases where it doesn't, since LinkedIn will itself reject/truncate an
            # over-limit InMail and a candidate should never be surprised by that after
            # already copying the text out of this app.

        return subject, body
