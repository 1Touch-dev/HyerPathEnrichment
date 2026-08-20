"""RQ worker tasks for job matching: fan-out scheduler, scan, score, explain, notify.

Pipeline shape (per phase2_module1.md §3 Decision 1):
    fan_out_daily_scans()  [cron, singleton]
        -> enqueues scan_jobs_for_candidate(user_id) per scan-enabled candidate, staggered
    scan_jobs_for_candidate(user_id)
        -> JobSpy scrape (reuses JobSpyEnricher's static scrape logic)
        -> dedup + upsert into job_postings (Decision 4)
        -> embed new/changed postings (job_posting_embeddings)
        -> pgvector similarity search against candidate's CV embedding (Decision 1, stage 1)
        -> rule-filter scoring (scorer.py, Decision 1 stage 2 + Decision 3)
        -> upsert job_matches
        -> generate_explanations_for_candidate(user_id) [only top-5, Decision 1/3]
        -> send_match_digest(user_id) [email, Decision 5/6]
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Import ORM registry FIRST to register all models with SQLAlchemy
import app.database.orm_registry  # noqa: F401
from app.database.session import SessionLocal, engine
from app.infrastructure.redis import close_redis
from app.modules.documents.models import CandidateDocument
from app.modules.job_matching import events, repository
from app.modules.job_matching.models import CandidateJobPreferences, JobPosting
from app.modules.job_matching.scorer import (
    compute_dedup_key,
    compute_overall_score,
    compute_rule_score,
)
from app.observability.cost_tracking import (
    track_embedding_cost,
    track_embedding_failure,
    track_llm_cost,
    track_llm_failure,
)
from app.observability.job_matching_metrics import (
    job_matching_digest_emails_sent_total,
    job_matching_explanations_generated_total,
    job_matching_postings_scraped_total,
    job_matching_push_notifications_total,
    job_matching_scan_duration_seconds,
    job_matching_scans_total,
    job_matching_webhook_notifications_total,
)

logger = logging.getLogger(__name__)


def fan_out_daily_scans() -> dict[str, int]:
    """Cron entrypoint (sync). Pages through scan-enabled candidates and enqueues one
    scan_jobs_for_candidate job per candidate, staggered across the day.

    Staggering: candidates are bucketed by `hash(user_id) % 24` into hourly RQ
    scheduled-enqueue offsets, so 10,000 candidates don't all hit JobSpy/pgvector
    in the same second (per architecture_phase2.md §4).
    """
    return asyncio.run(_fan_out_daily_scans_async())


async def _fan_out_daily_scans_async() -> dict[str, int]:
    from rq_scheduler import Scheduler

    from app.workers.queue import QUEUE_JOB_MATCHING, get_redis_connection

    enqueued = 0
    page_size = 200
    offset = 0
    # queue_name is required here: unlike Scheduler.cron() (which takes queue_name
    # per-call, see register_scheduled_jobs()), Scheduler.enqueue_at() always targets
    # the Scheduler instance's own configured queue. Without this, every staggered
    # scan job below would land in rq_scheduler's "default" queue instead of
    # job_matching — and the dedicated worker-job-matching container (which only
    # listens to job_matching) would never pick them up.
    scheduler = Scheduler(queue_name=QUEUE_JOB_MATCHING, connection=get_redis_connection())

    async with SessionLocal() as session:
        while True:
            prefs_page = await repository.list_scan_enabled_preferences(session, page_size, offset)
            if not prefs_page:
                break

            for prefs in prefs_page:
                bucket_hour = hash(str(prefs.user_id)) % 24
                scheduler.enqueue_at(
                    _now_plus_hours(bucket_hour),
                    scan_jobs_for_candidate,
                    str(prefs.user_id),
                    job_timeout=120,
                )
                enqueued += 1

            offset += page_size

    logger.info("Fanned out daily job-matching scans", extra={"enqueued": enqueued})
    return {"enqueued": enqueued}


def _now_plus_hours(hours: int) -> datetime:
    from datetime import UTC, timedelta

    return datetime.now(UTC) + timedelta(hours=hours)


def scan_jobs_for_candidate(user_id: str) -> dict[str, int]:
    """RQ entrypoint (sync) for a single candidate's job-matching scan."""
    return asyncio.run(_scan_jobs_for_candidate_async(user_id))


async def _scan_jobs_for_candidate_async(user_id: str) -> dict[str, int]:
    from app.clients.embeddings import get_embeddings_client
    from app.core.config import get_settings
    from app.enrichers.jobspy import JobSpyEnricher

    settings = get_settings()
    stats = {"scraped": 0, "new_postings": 0, "matches_scored": 0, "explanations": 0}
    scan_start = time.monotonic()

    try:
        async with SessionLocal() as session:
            prefs = await repository.get_preferences(session, UUID(user_id))
            if not prefs or not prefs.is_scan_enabled:
                logger.info(
                    "Skipping scan: preferences missing or disabled", extra={"user_id": user_id[:8]}
                )
                job_matching_scans_total.labels(status="skipped").inc()
                job_matching_scan_duration_seconds.observe(time.monotonic() - scan_start)
                return stats

            # Load candidate's CV data to build a search query and get their embedding.
            cv_doc = await _get_latest_cv(session, UUID(user_id))
            if not cv_doc:
                logger.info("Skipping scan: no processed CV found", extra={"user_id": user_id[:8]})
                job_matching_scans_total.labels(status="skipped").inc()
                job_matching_scan_duration_seconds.observe(time.monotonic() - scan_start)
                return stats

            search_term = _build_search_term(prefs, cv_doc)

            # Reuse JobSpyEnricher's scrape logic directly (Decision: not modifying the enricher class itself).
            enricher = JobSpyEnricher()
            location_arg: str | None = (
                prefs.desired_locations[0] if prefs.desired_locations else None
            )
            raw_rows = await asyncio.to_thread(
                enricher._scrape,
                search_term,
                location_arg,
                None,
                None,
                settings.job_matching_max_postings_per_scan,
                None,
            )
            stats["scraped"] = len(raw_rows)

            embeddings_client = get_embeddings_client()
            posting_ids: list[UUID] = []

            for row in raw_rows:
                title = str(row.get("title") or search_term)
                company = str(row.get("company") or "Unknown")
                location = row.get("location")
                remote = bool(row.get("is_remote") or row.get("remote") or False)
                source = str(row.get("site") or "jobspy")
                description = str(row.get("description") or "")

                dedup_key = compute_dedup_key(title, location, source)
                posting = await repository.upsert_job_posting(
                    session,
                    dedup_key,
                    {
                        "title": title,
                        "company": company,
                        "location": location,
                        "remote": remote,
                        "source": source,
                        "source_url": row.get("job_url"),
                        "description_raw": description,
                        "salary_min": _safe_int(row.get("min_amount")),
                        "salary_max": _safe_int(row.get("max_amount")),
                        "salary_currency": row.get("currency"),
                    },
                    source,
                )
                posting_ids.append(posting.id)
                job_matching_postings_scraped_total.labels(source=source).inc()

                # Embed new postings only (skip if embedding already exists is handled by upsert semantics).
                if description:
                    if await repository.has_posting_embedding(session, posting.id):
                        continue
                    try:
                        embedding, token_count = await embeddings_client.generate_embedding(
                            f"{title}\n{company}\n{description[:4000]}"
                        )
                    except Exception:
                        track_embedding_failure(model="text-embedding-3-small")
                        raise
                    await track_embedding_cost(
                        model="text-embedding-3-small", tokens=token_count, num_embeddings=1
                    )
                    await repository.store_posting_embedding(
                        session, posting.id, embedding, token_count
                    )
                    stats["new_postings"] += 1

            # Stage 1 (Decision 1): pgvector similarity search using the candidate's CV
            # embedding, restricted to just the postings scraped in this scan.
            cv_embedding = await _get_cv_embedding(session, cv_doc.id)

            if not cv_embedding:
                logger.info(
                    "No CV embedding available for scoring — skipping match scoring",
                    extra={"user_id": user_id[:8]},
                )
                stats["matches_scored"] = 0
            elif not posting_ids:
                logger.debug(
                    "No postings scraped this scan — skipping match scoring",
                    extra={"user_id": user_id[:8]},
                )
                stats["matches_scored"] = 0
            else:
                similar_postings = await repository.find_similar_postings(
                    session,
                    cv_embedding,
                    limit=settings.job_matching_max_postings_per_scan,
                    similarity_threshold=settings.job_matching_similarity_threshold,
                    posting_ids=posting_ids,
                )

                # Stage 2 (Decision 1 + Decision 3): deterministic rule filter on top of
                # the similarity-filtered candidates, then a weighted composite score.
                preferences_dict = {
                    "salary_min": prefs.salary_min,
                    "salary_max": prefs.salary_max,
                    "desired_locations": prefs.desired_locations or [],
                    "remote_preference": prefs.remote_preference,
                }

                matches_scored = 0
                for matched_posting_id, similarity_score, passed_threshold in similar_postings:
                    posting_row = await session.get(JobPosting, matched_posting_id)
                    if posting_row is None:
                        # Defensive: posting could theoretically have been removed between
                        # the scrape/upsert pass above and this scoring pass.
                        continue

                    posting_dict = {
                        "salary_min": posting_row.salary_min,
                        "salary_max": posting_row.salary_max,
                        "location": posting_row.location,
                        "remote": posting_row.remote,
                    }
                    rule_score, breakdown = compute_rule_score(posting_dict, preferences_dict)
                    overall_score = compute_overall_score(similarity_score, rule_score)
                    if not passed_threshold:
                        breakdown["below_similarity_threshold"] = True

                    await repository.upsert_match(
                        session,
                        UUID(user_id),
                        matched_posting_id,
                        similarity_score,
                        rule_score,
                        overall_score,
                        breakdown,
                    )
                    matches_scored += 1

                stats["matches_scored"] = matches_scored

            # Live unread-count push (SSE): unconditional after a completed scan — even
            # when matches_scored == 0, the count could have shifted because matches were
            # viewed elsewhere since the last scan. Skipped entirely on the early returns
            # above (missing/disabled prefs, no CV), since nothing changed in those cases.
            unread_count = await repository.count_unread_matches(session, UUID(user_id))
            await events.publish_unread_count(user_id, unread_count)

        # Second pass: generate explanations for top-5 unexplained matches (Decision 1/3).
        exp_stats = await _generate_explanations_for_candidate_async(user_id)
        stats["explanations"] = exp_stats["generated"]

        # Third pass: send digest notification if there are new, unnotified matches.
        await _send_match_digest_async(user_id)

        job_matching_scans_total.labels(status="success").inc()
        job_matching_scan_duration_seconds.observe(time.monotonic() - scan_start)
        return stats

    finally:
        await close_redis()
        await engine.dispose()


def _build_search_term(prefs: CandidateJobPreferences, cv_doc: CandidateDocument) -> str:
    """Prefer explicit desired_roles; fall back to CV's current_role."""
    if prefs.desired_roles:
        return str(prefs.desired_roles[0])
    extracted = cv_doc.extracted_data or {}
    return str(extracted.get("current_role") or "software engineer")


async def _get_latest_cv(session: AsyncSession, user_id: UUID) -> CandidateDocument | None:
    result = await session.execute(
        select(CandidateDocument)
        .where(
            CandidateDocument.user_id == user_id,
            CandidateDocument.document_type == "cv",
            CandidateDocument.processing_status == "completed",
        )
        .order_by(CandidateDocument.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_cv_embedding(session: AsyncSession, document_id: UUID) -> list[float] | None:
    from app.modules.documents.models import DocumentEmbedding

    result = await session.execute(
        select(DocumentEmbedding).where(DocumentEmbedding.document_id == document_id).limit(1)
    )
    emb = result.scalar_one_or_none()
    return list(emb.embedding) if emb else None


def _safe_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)  # type: ignore[call-overload,no-any-return]
    except (TypeError, ValueError):
        return None


def generate_explanations_for_candidate(user_id: str) -> dict[str, int]:
    """RQ entrypoint (sync)."""
    return asyncio.run(_generate_explanations_for_candidate_async(user_id))


async def _generate_explanations_for_candidate_async(user_id: str) -> dict[str, int]:
    """Per Decision 1/3: only the top-N unexplained matches get an LLM call.

    Claim/save/record-failure state machine: each match is atomically claimed
    (explanation_status 'not_explained' -> 'processing') before the LLM call, so a
    match already claimed by a concurrent pass is skipped rather than double-processed.
    On success the match is saved as 'explained'; on failure the attempt is recorded
    and the match is requeued ('not_explained') or capped ('failed') once
    `job_matching_explanation_max_retries` is reached.
    """
    from app.core.config import get_settings
    from app.modules.job_matching.explainer import generate_match_explanation

    settings = get_settings()
    generated = 0

    async with SessionLocal() as session:
        top_matches = await repository.get_top_unexplained_matches(
            session, UUID(user_id), settings.job_matching_top_n_explanations
        )
        for match, posting in top_matches:
            claimed = await repository.claim_match_for_explanation(session, match.id)
            if not claimed:
                continue

            try:
                explanation, token_usage = await generate_match_explanation(
                    match, posting, settings
                )
                await repository.save_explanation(session, match.id, explanation)
                await track_llm_cost(
                    model="gpt-4o-mini",
                    input_tokens=token_usage["input_tokens"],
                    output_tokens=token_usage["output_tokens"],
                    operation="job_match_explanation",
                )
                generated += 1
                job_matching_explanations_generated_total.inc()
            except Exception as exc:
                track_llm_failure(model="gpt-4o-mini", operation="job_match_explanation")
                logger.warning(
                    "Failed to generate match explanation",
                    exc_info=True,
                    extra={"match_id": str(match.id), "user_id": user_id[:8]},
                )
                await repository.record_explanation_failure(
                    session,
                    match.id,
                    error_message=str(exc),
                    max_retries=settings.job_matching_explanation_max_retries,
                )

    return {"generated": generated}


def send_match_digest(user_id: str) -> dict[str, int]:
    """RQ entrypoint (sync)."""
    return asyncio.run(_send_match_digest_async(user_id))


async def _send_match_digest_async(user_id: str) -> dict[str, int]:
    """Send a digest notification for unnotified matches via every channel the
    candidate has actually enabled, then mark them notified.

    Per Decision 6: 'email', 'webhook', and 'push' channels are wired; 'sms' is
    accepted but logged as a no-op, matching notify.py's fail-soft convention.
    Webhook delivery additionally requires a candidate-configured `webhook_url` —
    without one, the 'webhook' channel is treated as a no-op just like 'sms'.
    'push' delivery requires at least one registered `PushSubscription` row;
    without one it's a no-op too.

    Each channel below is gated independently on its own membership in
    `prefs.notification_channels` — a candidate who only enabled "webhook" (or
    only "push"), having unchecked "email", must still get that channel's
    dispatch. The digest is only skipped up front when there's nothing to
    notify about (`top_5` empty) or preferences/the user row are missing —
    never based on which specific channel happens to be enabled.

    If a candidate has no deliverable channel enabled at all (e.g. only "sms",
    or none), the top-5 matches are still marked notified as "seen but not
    delivered" rather than left to re-surface in every future digest forever —
    the same fail-soft convention already used when a webhook/push delivery
    itself fails (see the webhook/push failure tests below).
    """
    from app.clients.notify import notify_job_match
    from app.modules.job_matching import push
    from app.workers.queue import enqueue_email

    async with SessionLocal() as session:
        prefs = await repository.get_preferences(session, UUID(user_id))
        if not prefs:
            return {"sent": 0}

        rows, _total = await repository.list_matches_for_user(
            session, UUID(user_id), limit=100, offset=0
        )
        unnotified = [(m, p) for m, p in rows if m.notified_at is None]

        if not unnotified:
            return {"sent": 0}

        top_5 = unnotified[:5]

        if "sms" in prefs.notification_channels:
            logger.info(
                "SMS notification requested but not implemented (Decision 6) — skipping",
                extra={"user_id": user_id[:8], "channels": prefs.notification_channels},
            )

        match_payload = [
            {
                "title": p.title,
                "company": p.company,
                "overall_score": m.overall_score,
                "source_url": p.source_url or "",
            }
            for m, p in top_5
        ]

        if "email" in prefs.notification_channels:
            # Fetch user email via auth module (read-only cross-module read of the User row —
            # allowed per RULE.md: modules may read shared domain/auth records; no service coupling).
            from app.auth.models import User

            user = await session.get(User, UUID(user_id))
            if user:
                enqueue_email(
                    template="job_match_digest",
                    recipient=user.email,
                    context={
                        "matches": [
                            {
                                "title": p.title,
                                "company": p.company,
                                "location": p.location,
                                "overall_score": m.overall_score,
                                "explanation": m.explanation or "",
                                "source_url": p.source_url or "",
                            }
                            for m, p in top_5
                        ],
                    },
                )
                job_matching_digest_emails_sent_total.inc()

        if "webhook" in prefs.notification_channels and prefs.webhook_url:
            webhook_sent = await notify_job_match(
                webhook_url=prefs.webhook_url,
                candidate_id=user_id,
                matches=match_payload,
            )
            job_matching_webhook_notifications_total.labels(
                status="success" if webhook_sent else "failed"
            ).inc()
        elif "webhook" in prefs.notification_channels:
            logger.info(
                "Webhook notification requested but no webhook_url configured — skipping",
                extra={"user_id": user_id[:8]},
            )

        if "push" in prefs.notification_channels:
            subscriptions = await repository.list_subscriptions_for_user(session, UUID(user_id))
            if subscriptions:
                push_payload = {
                    "source": "hyrepath-job-matching",
                    "event": "job_match_digest",
                    "candidate_id": user_id,
                    "matches": match_payload,
                }
                for subscription in subscriptions:
                    push_sent = await push.send_push_notification(subscription, push_payload)
                    job_matching_push_notifications_total.labels(
                        status="success" if push_sent else "failed"
                    ).inc()
            else:
                logger.info(
                    "Push notification requested but no subscriptions registered — skipping",
                    extra={"user_id": user_id[:8]},
                )

        await repository.mark_notified(session, [m.id for m, _ in top_5])
        return {"sent": len(top_5)}


def check_worker_health(queue_name: str) -> bool:
    """Health check for the job-matching worker, matching document.py's pattern."""
    try:
        from rq import Queue

        from app.workers.queue import get_redis_connection

        redis_conn = get_redis_connection()
        redis_conn.ping()
        queue = Queue(queue_name, connection=redis_conn)
        queue_len = len(queue)
        logger.debug(f"Health check: queue {queue_name} has {queue_len} jobs")
        return True
    except Exception as exc:
        logger.error(f"Health check failed: {exc}", exc_info=True)
        return False
