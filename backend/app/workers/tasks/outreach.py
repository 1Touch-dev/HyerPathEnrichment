"""RQ worker task: generate an outreach draft using Perplexity company context + GPT-4o (Decision 5)."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Literal
from uuid import UUID, uuid4

import httpx
from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import app.database.orm_registry  # noqa: F401
from app.clients.perplexity import PerplexityClient
from app.clients.retry import with_transient_retry
from app.core.config import Settings, get_settings
from app.database.session import SessionLocal, engine
from app.domain.candidate import CVData
from app.infrastructure.redis import close_redis
from app.modules.admin.ai_supervision_service import record_ai_action
from app.modules.admin.moderation_flagging import flag_if_needed
from app.modules.demand_intelligence.service import get_top_countries_for_role
from app.modules.documents.models import CandidateDocument

# JobMatch/JobPosting are owned by the job_matching module — imported here
# read-only, never redefined, same cross-module convention job_swipe/repository.py
# already uses for its own read-only access to Module 1's tables.
from app.modules.job_matching.models import JobMatch, JobPosting
from app.modules.outreach.models import EmployerCompanyTier, OutreachMessage
from app.modules.outreach.repository import get_company_tier
from app.modules.outreach.service import apply_classified_company_tier
from app.observability.outreach_metrics import outreach_drafts_by_type_total
from app.workers.queue import get_redis_connection

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

_STRATEGY_INSTRUCTIONS = {
    "direct_pitch": "State your interest and relevant qualifications plainly and ask for a conversation.",
    "value_first": "Open by naming one specific, concrete way you could help this company (grounded in the job description or company context provided) before mentioning your own qualifications.",
    "curiosity": "Open with a genuine, specific question about the company or role that invites a reply, rather than opening with a pitch about yourself.",
    "warm_referral": "Reference the referral/connection context provided below naturally near the opening of the message.",
}

_ROLE_TYPE_INSTRUCTIONS = {
    (
        "technical",
        "senior",
    ): "Speak with technical specificity and treat the recipient as a peer who can evaluate technical depth directly; keep it concise and skip generic enthusiasm.",
    (
        "technical",
        "junior",
    ): "Keep technical references accessible; a junior technical hiring contact may be screening on behalf of others rather than evaluating deep technical fit themselves.",
    (
        "non_technical",
        "senior",
    ): "Lead with business impact and outcomes rather than technical detail; a senior non-technical contact evaluates fit/communication/culture signals more than technical depth.",
    (
        "non_technical",
        "junior",
    ): "Keep the message simple, warm, and outcome-focused; avoid jargon a junior non-technical screener may not be positioned to evaluate.",
}

_COMPANY_TIER_INSTRUCTIONS = {
    "premium": "This is a well-known, high-profile employer the candidate is likely already "
    "familiar with. Skip generic company introductions or explaining what the company does — "
    "assume the reader already knows their own employer's reputation. Lead with a sharp, specific "
    "value proposition and keep the tone confident and concise; avoid sounding star-struck or "
    "overly deferential toward a 'prestigious' employer.",
    "outsourcing": "This is a staffing/outsourcing employer, where the hiring contact may field "
    "many generic, low-effort candidate messages. Make genuine interest explicit and warm rather "
    "than assumed — name a specific reason this particular role/company is a fit, rather than a "
    "tone that could be mistaken for a mass-sent template.",
}

# Sibling to _STRATEGY_INSTRUCTIONS/_ROLE_TYPE_INSTRUCTIONS/_COMPANY_TIER_INSTRUCTIONS
# above (co-located with classify_company_tier itself would also read fine; kept
# here since it's a plain constant like its siblings, not classifier-specific logic).
_COMPANY_TIER_CLASSIFIER_SYSTEM_PROMPT = (
    "You classify a company into exactly one of two tiers based on its size and "
    "niche, using only the public company context provided. "
    '"premium": a well-known, established, or high-paying employer (e.g. a large '
    "company, a recognized brand, a well-funded/well-regarded firm in its niche). "
    '"outsourcing": a staffing/outsourcing/body-shop employer, or any company too '
    "small/obscure/context-poor to confidently call premium. When genuinely "
    'uncertain, prefer "outsourcing" — it is the more conservative default. '
    'Respond with a JSON object: {"tier": "premium" | "outsourcing"}.'
)

# Structured-output JSON schema for classify_company_tier — OpenAI's
# response_format={"type": "json_schema", ...} strict mode, not free-text
# parsed with json.loads on a hope (matches this file's existing httpx +
# with_transient_retry call shape used by _draft_with_llm for consistency).
_COMPANY_TIER_JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "company_tier",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "tier": {"type": "string", "enum": ["premium", "outsourcing"]},
            },
            "required": ["tier"],
            "additionalProperties": False,
        },
    },
}


async def classify_company_tier(
    company_name: str, company_context: str
) -> Literal["premium", "outsourcing"]:
    """LLM-based company-tier classifier (confirmed by leadership 2026-08-26:
    "automate classifier w llm based on company size and niche"). company_context
    is the same public-company-summary string this module already fetches via
    PerplexityClient.get_company_context(company_name, role_title) — see
    backend/app/clients/perplexity.py's get_company_context, reused here as-is,
    not re-fetched by a second research call.

    Never raises: on ANY failure mode -- network/HTTP exception, a
    schema-invalid/unparseable response, or a refusal -- this fails soft by
    returning "outsourcing" (the more conservative, less-differentiated tier;
    see 03-outreach-strategy-dimension.md's "Ambiguities resolved" for why that
    default, not "premium", is the safe fallback) rather than blocking
    drafting.
    """
    settings = get_settings()
    api_key = settings.openai_api_key.strip()
    if not api_key:
        return "outsourcing"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Same call shape as _draft_with_llm below: raise_for_status() must
            # run *inside* the retried operation, not after with_transient_retry
            # returns, so status-code errors (429/502/503/504) actually trigger
            # a retry, not just network-level failures.
            async def _do_post() -> httpx.Response:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": _COMPANY_TIER_CLASSIFIER_SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": (
                                    f"Company: {company_name}\n"
                                    f"Public company context: {company_context or '(none available)'}"
                                ),
                            },
                        ],
                        "response_format": _COMPANY_TIER_JSON_SCHEMA,
                        "temperature": 0.0,
                    },
                )
                resp.raise_for_status()
                return resp

            response = await with_transient_retry(_do_post)
            result = response.json()
            choice = result["choices"][0]["message"]
            # A refusal surfaces via the "refusal" field in structured-output
            # mode rather than "content" — treat it the same as any other
            # unparseable-response failure mode.
            if choice.get("refusal"):
                return "outsourcing"
            content = choice["content"]
            parsed = json.loads(content)
            tier = parsed["tier"]
            if tier == "premium":
                return "premium"
            return "outsourcing"
    except Exception:
        logger.warning(
            "classify_company_tier failed; failing soft to 'outsourcing'",
            exc_info=True,
            extra={"company_name": company_name},
        )
        return "outsourcing"


# Bounds on how long a draft job will wait for a concurrent draft-to-the-same-
# -company classification to finish before falling back to classifying
# locally itself -- see _classify_and_persist_company_tier below (Issue #4).
_COMPANY_TIER_LOCK_TTL_SECONDS = 15
_COMPANY_TIER_LOCK_POLL_INTERVAL_SECONDS = 0.2
_COMPANY_TIER_LOCK_POLL_MAX_ATTEMPTS = 10  # ~2s total wait


async def _classify_and_persist_company_tier(
    session: AsyncSession, company_name: str, company_context: str
) -> EmployerCompanyTier:
    """Classify and persist a brand-new company's tier row, guarded by a
    Redis lock keyed on ``company_name`` (Issue #4, cross-recruiter race).

    Without this, two concurrent draft requests for the same not-yet-tiered
    employer (e.g. from two different recruiters/candidates) could both see
    no existing ``EmployerCompanyTier`` row in
    ``_generate_outreach_draft_job``, both call ``classify_company_tier``,
    and both attempt to insert a row via ``apply_classified_company_tier`` --
    only one can win the unique constraint on ``EmployerCompanyTier.company_name``,
    crashing the loser's draft job with an unhandled ``IntegrityError``.

    Reuses the exact ``SET NX EX`` lock primitive
    ``OutreachService.request_draft`` already uses for its own per-draft
    lock (see ``app/modules/outreach/service.py``), via the same
    ``get_redis_connection()`` helper -- this worker module had no other
    Redis usage before this.

    Lock-holder path: classify, persist, release.

    Non-lock-holder path: poll ``get_company_tier`` every ~200ms for up to
    ~2s (bounded -- this can never block indefinitely). If a row appears in
    the meantime, use it. If the wait times out with still no row (e.g. the
    lock holder crashed or is unusually slow), fall back to classifying
    locally rather than blocking the draft forever.

    Either path also wraps the ``apply_classified_company_tier`` call in a
    defensive ``try/except IntegrityError`` backstop: even with the lock
    above, a duplicate-key race is still theoretically possible (lock TTL
    expiring mid-write, or the no-lock fallback path racing the original
    holder's own write) -- on that exception, re-read and return the
    now-existing row instead of letting the draft job crash.
    """
    lock_key = f"company-tier-classify-lock:{company_name.strip().lower()}"
    redis_conn = None
    lock_acquired = False
    try:
        redis_conn = get_redis_connection()
        lock_acquired = bool(
            redis_conn.set(lock_key, "1", nx=True, ex=_COMPANY_TIER_LOCK_TTL_SECONDS)
        )
    except RedisError:
        # Lock is only a race guard. If Redis is down (CI, outage), classify
        # locally rather than crashing the draft — IntegrityError below is the
        # remaining backstop for a duplicate insert.
        logger.warning("company-tier classify lock unavailable; classifying locally")
        lock_acquired = True
        redis_conn = None

    if not lock_acquired:
        for _ in range(_COMPANY_TIER_LOCK_POLL_MAX_ATTEMPTS):
            await asyncio.sleep(_COMPANY_TIER_LOCK_POLL_INTERVAL_SECONDS)
            existing = await get_company_tier(session, company_name)
            if existing is not None:
                return existing
        # Timed out waiting for the lock holder to finish -- fall back to
        # classifying locally below rather than waiting indefinitely.

    try:
        classified_tier = await classify_company_tier(company_name, company_context)
        try:
            return await apply_classified_company_tier(session, company_name, classified_tier)
        except IntegrityError:
            await session.rollback()
            existing = await get_company_tier(session, company_name)
            if existing is not None:
                return existing
            raise
    finally:
        if lock_acquired and redis_conn is not None:
            try:
                redis_conn.delete(lock_key)
            except RedisError:
                logger.warning("company-tier classify lock release failed")


def generate_outreach_draft_job(
    user_id: str,
    document_id: str,
    company_name: str,
    role_title: str | None,
    job_match_id: str | None,
    message_type: str = "email",
    custom_instruction: str | None = None,
    job_description: str | None = None,
    strategy: str = "direct_pitch",
    referral_context: str | None = None,
    role_type: str | None = None,
    seniority: str | None = None,
    recipient_email: str | None = None,
    recipient_linkedin_url: str | None = None,
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
            job_description,
            strategy,
            referral_context,
            role_type,
            seniority,
            recipient_email,
            recipient_linkedin_url,
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
    job_description: str | None = None,
    strategy: str = "direct_pitch",
    referral_context: str | None = None,
    role_type: str | None = None,
    seniority: str | None = None,
    recipient_email: str | None = None,
    recipient_linkedin_url: str | None = None,
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

            # Pasted JD wins when provided; otherwise load from the tracked match.
            resolved_jd = (job_description or "").strip() or None
            if resolved_jd:
                resolved_jd = resolved_jd[:1500]
            else:
                resolved_jd = await _get_job_description(session, job_match_id, UUID(user_id))

            perplexity = PerplexityClient()
            context = await perplexity.get_company_context(company_name, role_title)

            settings = get_settings()
            # Gating the get_company_tier() lookup itself behind the flag (not just
            # its use in the prompt) — this repo's chosen resolution of the
            # ambiguity noted in 03-outreach-strategy-dimension.md's "Verification"
            # section ("either is defensible; be consistent and explicit"). This
            # also means zero extra DB calls when the flag is off, matching this
            # plan's stricter regression bar for 03's company-tier section.
            tier: str | None = None
            if settings.enable_company_tier_in_outreach_drafting:
                tier_row = await get_company_tier(session, company_name)
                if tier_row is not None:
                    tier = tier_row.tier
                else:
                    # No row yet for this employer — classify lazily as a
                    # side effect of this draft rather than requiring a
                    # recruiter to set the tier manually first (machine-2/03,
                    # "LLM-based company-tier classifier"). classify_company_tier
                    # never raises (fails soft to "outsourcing"), and
                    # apply_classified_company_tier enforces the
                    # override-preservation rule before persisting.
                    # _classify_and_persist_company_tier additionally guards
                    # this against the cross-recruiter race where two
                    # concurrent drafts for the same brand-new company both
                    # try to insert a row (Issue #4).
                    tier_row = await _classify_and_persist_company_tier(
                        session, company_name, context["summary"]
                    )
                    tier = tier_row.tier

            subject, body = await _draft_with_llm(
                cv_data,
                company_name,
                role_title,
                context["summary"],
                resolved_jd,
                settings,
                message_type,
                custom_instruction,
                strategy,
                referral_context,
                role_type,
                seniority,
                tier,
                db=session,
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
                strategy=strategy,
                referral_context=referral_context,
                role_type=role_type,
                seniority=seniority,
                recipient_email=recipient_email,
                recipient_linkedin_url=recipient_linkedin_url,
            )
            session.add(message)
            await session.commit()

            await record_ai_action(
                session,
                action_type="outreach_draft",
                candidate_user_id=UUID(user_id),
                related_id=message.id,
                summary=f"Outreach draft generated for {company_name}",
            )

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

            # Soft-moderation flagging (Batch 1 admin module): runs after the
            # draft's own success is already committed, so a flagging failure
            # can never affect draft generation. flag_if_needed is internally
            # fail-open (see moderation_flagging.py), but this call site still
            # wraps it defensively: the test suite mocks flag_if_needed
            # directly, which bypasses that internal safety net entirely, so
            # this try/except is the only thing guaranteeing a broken/changed
            # flagging implementation can never break outreach draft
            # generation.
            try:
                await flag_if_needed(
                    session,
                    resource_type="outreach_message",
                    resource_id=message.id,
                    text_fields=[subject, body],
                )
            except Exception:
                logger.warning(
                    "flag_if_needed raised unexpectedly; ignoring (fail-open)",
                    exc_info=True,
                    extra={"user_id": user_id[:8], "message_id": str(message.id)},
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


async def _demand_context_line(
    cv_data: CVData, settings: Settings, db: AsyncSession | None
) -> str | None:
    """One short, factual line about job-market demand for the candidate's first
    desired role with actual snapshot data, or None if the flag is off, no
    desired_roles are set, or no snapshot data exists for any of them. Checks only
    the first desired_roles entry with data (not all of them) to keep the prompt
    addition genuinely short, per this chunk's "small, additive" scope."""
    if not settings.enable_demand_intelligence_in_outreach or not cv_data.desired_roles:
        return None
    if db is None:
        return None
    for role in cv_data.desired_roles:
        snapshots = await get_top_countries_for_role(db, role, limit=3)
        if snapshots:
            countries = ", ".join(s.country_iso2.upper() for s in snapshots)
            return (
                f"Note: recent job-market data shows the highest current demand for "
                f"{role} is in {countries}; consider this when discussing relocation/"
                f"remote flexibility, if relevant."
            )
    return None


async def _draft_with_llm(
    cv_data: CVData,
    company_name: str,
    role_title: str | None,
    company_context: str,
    job_description: str | None,
    settings: Settings,
    message_type: str = "email",
    custom_instruction: str | None = None,
    strategy: str = "direct_pitch",
    referral_context: str | None = None,
    role_type: str | None = None,
    seniority: str | None = None,
    company_tier: str | None = None,
    db: AsyncSession | None = None,
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

    strategy_fragment = _STRATEGY_INSTRUCTIONS.get(strategy, _STRATEGY_INSTRUCTIONS["direct_pitch"])
    user_content = f"{user_content}\n{strategy_fragment}"

    demand_line = await _demand_context_line(cv_data, settings, db)
    if demand_line:
        user_content = f"{user_content}\n{demand_line}"

    if role_type is not None and seniority is not None:
        role_type_fragment = _ROLE_TYPE_INSTRUCTIONS.get((role_type, seniority))
        if role_type_fragment:
            user_content = f"{user_content}\n{role_type_fragment}"

    company_tier_fragment = (
        _COMPANY_TIER_INSTRUCTIONS.get(company_tier) if company_tier is not None else None
    )
    if company_tier_fragment:
        user_content = f"{user_content}\n{company_tier_fragment}"

    if message_type == "custom" and custom_instruction:
        user_content = f"{user_content}\n\n{_CUSTOM_INSTRUCTION_PREFIX}\n{custom_instruction}"

    if strategy == "warm_referral" and referral_context:
        user_content = f"{user_content}\n\nReferral/connection context: {referral_context}"

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
