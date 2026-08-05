"""Enrichment execution engine — sole owner of run / dispatch / merge orchestration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.llm import LiteLLMDisambiguator
from app.compliance.audit import log_event
from app.compliance.identifiers import hash_identifier, hashes_from_request
from app.compliance.purge import PurgeResult, purge_identifier_data
from app.compliance.suppression import (
    add_suppression,
    check_suppression,
    is_request_suppressed,
)
from app.core.config import get_settings
from app.domain.dossier import ConfidenceBreakdown, Dossier, SocialHandle
from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import AuditEventType, JobStatus, RequestedTier
from app.enrichers._shared import common_email_patterns, slugify_domain
from app.enrichers.base import Enricher
from app.enrichers.disambiguate import disambiguate_handles
from app.enrichers.merge import base_dossier, build_confidence, merge_payloads
from app.enrichers.registry import (
    email_verify_enricher,
    tier1_enrichers,
    tier2_enrichers,
    tier3_discover_enrichers,
    tier4_enrichers,
)
from app.modules.enrichment.job_events import publish_job_status
from app.modules.enrichment.models import JobRecord
from app.modules.enrichment.repository import JobRepository

logger = logging.getLogger(__name__)


class Pipeline:
    """Owns enrichment execution. Sync and async both converge here."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.jobs = JobRepository(db)
        self.llm = LiteLLMDisambiguator()
        self.tier1 = tier1_enrichers()
        self.tier2 = tier2_enrichers()
        self.tier3_discover = tier3_discover_enrichers()
        self._email_verify = email_verify_enricher()
        self.tier4 = tier4_enrichers()

    async def run(self, request: EnrichmentRequest, user_id: UUID | None = None) -> JobRecord:
        """Synchronous path: create a job and run the pipeline inline."""
        job = await self.jobs.create(request, JobStatus.running, user_id=user_id)
        await self.jobs.flush()
        return await self._execute(job, request, sync_mode=True)

    async def create_queued_job(
        self, request: EnrichmentRequest, user_id: UUID | None = None
    ) -> JobRecord:
        """Async path: persist a queued job for a worker to pick up later."""
        if await is_request_suppressed(self.db, request):
            return await self._create_suppressed_job(request, user_id=user_id)

        job = await self.jobs.create(request, JobStatus.queued, user_id=user_id)
        await self.jobs.commit()
        await self.jobs.refresh(job)
        return job

    async def is_request_suppressed(self, request: EnrichmentRequest) -> bool:
        return await is_request_suppressed(self.db, request)

    async def create_suppressed_job(
        self, request: EnrichmentRequest, user_id: UUID | None = None
    ) -> JobRecord:
        return await self._create_suppressed_job(request, user_id=user_id)

    async def _create_suppressed_job(
        self, request: EnrichmentRequest, user_id: UUID | None = None
    ) -> JobRecord:
        job = await self.jobs.create(request, JobStatus.suppressed, user_id=user_id)
        dossier = base_dossier(request)
        dossier.metadata["suppressed"] = True
        await self.jobs.mark_status(
            job,
            JobStatus.suppressed,
            dossier_payload=dossier.model_dump(mode="json"),
            commit=False,
        )

        request_hashes = hashes_from_request(request)
        if request_hashes:
            await log_event(
                self.db,
                AuditEventType.enrichment_suppressed,
                request_hashes[0],
                job_id=job.id,
            )

        await self.jobs.commit()
        await self.jobs.refresh(job)
        await publish_job_status(job.id, JobStatus.suppressed)
        return job

    async def execute_job(self, job_id: str) -> JobRecord | None:
        """Worker path: load a queued job by id and run the pipeline."""
        job = await self.jobs.get(job_id)
        if job is None:
            logger.warning("execute_job called for unknown job")
            return None

        # If this is a child job, handle it specially
        if job.parent_job_id:
            return await self._execute_child_job(job)

        request = EnrichmentRequest.model_validate(job.request_payload)
        # Commit the running transition immediately rather than leaving it as a
        # dirty attribute: autoflush would otherwise open an uncommitted write
        # transaction on this session that isn't closed until mark_status runs
        # at the very end of _execute. Tier 1 enrichers (LinkedIn photo) take
        # 30-90s per profile and write to photo_cache on their own session —
        # seen live during the Tier 1 canary: that second writer hit "database
        # is locked" on every successful scrape because this session's
        # long-held, uncommitted lock outlasted SQLite's busy_timeout.
        job = await self.jobs.mark_status(job, JobStatus.running)
        try:
            return await self._execute(job, request, sync_mode=False)
        except Exception as exc:
            logger.error(
                "job execution failed",
                exc_info=True,
                extra={"job_id": job_id, "exception_type": type(exc).__name__},
            )
            await self.jobs.rollback()
            failed = await self.jobs.get(job_id)
            if failed is not None:
                await self.jobs.mark_status(failed, JobStatus.failed)
                await publish_job_status(job_id, JobStatus.failed)
            raise

    async def create_parent_job(
        self, request: EnrichmentRequest, user_id: UUID | None = None
    ) -> JobRecord:
        """Create a parent job that orchestrates children."""
        job = await self.jobs.create(request, JobStatus.running, user_id=user_id)
        await self.jobs.flush()
        return job

    async def create_child_job(
        self, parent: JobRecord, request: EnrichmentRequest, tier_assignment: list[str]
    ) -> JobRecord:
        """Create a child job assigned to specific tiers."""
        child = await self.jobs.create_child_job(parent, request, tier_assignment)
        await self.jobs.flush()
        return child

    async def _execute_child_job(self, child_job: JobRecord) -> JobRecord:
        """Execute child job with assigned tiers only."""
        request = EnrichmentRequest.model_validate(child_job.request_payload)

        # Override requested_tiers with child's assignment
        tier_assignment = [RequestedTier(t) for t in (child_job.tier_assignment or [])]
        request.requested_tiers = tier_assignment

        child_job = await self.jobs.mark_status(child_job, JobStatus.running)

        try:
            result = await self._execute(child_job, request, sync_mode=False)

            # After completion, check if we can merge into parent
            await self._try_merge_into_parent(child_job)

            return result
        except Exception:
            # Mark child as failed, but don't fail parent yet
            await self.jobs.mark_status(child_job, JobStatus.failed)
            await self._check_parent_completion(child_job.parent_job_id)
            raise

    async def _try_merge_into_parent(self, completed_child: JobRecord) -> None:
        """Attempt to merge child results into parent if all children complete."""
        if not completed_child.parent_job_id:
            return

        # Check if all siblings are done
        if not await self.jobs.all_children_complete(completed_child.parent_job_id):
            return

        # All children complete - merge results
        parent = await self.jobs.get(completed_child.parent_job_id)
        if not parent:
            return

        children: List[JobRecord] = await self.jobs.get_children(parent.id)

        # Merge all child dossiers
        merged_dossier = self._merge_child_dossiers(
            [Dossier.model_validate(child.dossier_payload) for child in children]
        )

        # Determine parent status (completed if any child succeeded, failed if all failed)
        any_completed = any(child.status == JobStatus.completed.value for child in children)
        parent_status = JobStatus.completed if any_completed else JobStatus.failed

        await self.jobs.mark_status(
            parent,
            parent_status,
            dossier_payload=merged_dossier.model_dump(mode="json"),
        )

    async def _check_parent_completion(self, parent_job_id: str | None) -> None:
        """Check if parent should be marked as complete/failed after child fails."""
        if not parent_job_id:
            return

        if await self.jobs.all_children_complete(parent_job_id):
            await self._try_merge_into_parent_by_id(parent_job_id)

    async def _try_merge_into_parent_by_id(self, parent_job_id: str) -> None:
        """Helper to merge when we only have parent ID."""
        parent = await self.jobs.get(parent_job_id)
        if not parent:
            return

        children: List[JobRecord] = await self.jobs.get_children(parent.id)
        if not children:
            return

        # Use the first child to trigger merge logic
        await self._try_merge_into_parent(children[0])

    def _merge_child_dossiers(self, child_dossiers: list[Dossier]) -> Dossier:
        """Merge multiple child dossiers into one parent dossier."""
        merged = Dossier()

        for child_dossier in child_dossiers:
            # Merge photo (take first non-null)
            if child_dossier.photo and not merged.photo:
                merged.photo = child_dossier.photo

            # Merge handles (deduplicate)
            for handle in child_dossier.handles:
                key = (handle.platform.lower(), handle.username.lower())
                if not any((h.platform.lower(), h.username.lower()) == key for h in merged.handles):
                    merged.handles.append(handle)

            # Merge emails (deduplicate)
            for email in child_dossier.emails:
                if email not in merged.emails:
                    merged.emails.append(email)

            # Merge verified_emails (deduplicate by value)
            for verified in child_dossier.verified_emails:
                if not any(
                    v.value.lower() == verified.value.lower() for v in merged.verified_emails
                ):
                    merged.verified_emails.append(verified)

            # Merge github
            if child_dossier.github and not merged.github:
                merged.github = child_dossier.github

            # Merge coworkers (deduplicate)
            for coworker in child_dossier.coworkers:
                if coworker not in merged.coworkers:
                    merged.coworkers.append(coworker)

            # Merge jobs (deduplicate by normalize key)
            for job in child_dossier.jobs:
                # Simple deduplication - could use normalize_job_key from merge.py
                if job not in merged.jobs:
                    merged.jobs.append(job)

            # Merge business (take first non-null)
            if child_dossier.business and not merged.business:
                merged.business = child_dossier.business

            # Merge sources (deduplicate)
            for source in child_dossier.sources:
                if source not in merged.sources:
                    merged.sources.append(source)

            # Merge confidence (take from first child or recalculate)
            if child_dossier.confidence and not merged.confidence:
                merged.confidence = child_dossier.confidence

            # Merge metadata
            merged.metadata.update(child_dossier.metadata)

        return merged

    async def _execute(
        self,
        job: JobRecord,
        request: EnrichmentRequest,
        *,
        sync_mode: bool = False,
    ) -> JobRecord:
        if await is_request_suppressed(self.db, request):
            dossier = base_dossier(request)
            dossier.metadata["suppressed"] = True
            return await self.jobs.mark_status(
                job,
                JobStatus.suppressed,
                dossier_payload=dossier.model_dump(mode="json"),
            )

        payloads = await self._dispatch(request, sync_mode=sync_mode)
        # #region agent log
        logger.info(
            "[DEBUG-85dffc] _dispatch completed",
            extra={
                "payload_count": len(payloads),
                "empty_payloads": sum(1 for p in payloads if not p or p == {}),
                "hypothesisId": "C",
            },
        )
        # #endregion
        dossier = await self._merge(request, payloads)

        # Determine if we found any REAL enrichment data
        # Sources alone don't count as data - they just indicate which enrichers ran
        # Empty github/business objects also don't count as real data
        has_real_data = (
            dossier.photo is not None
            or len(dossier.handles) > 0
            or len(dossier.emails) > 0
            or len(dossier.verified_emails) > 0
            or (
                dossier.business is not None
                and any(
                    [
                        dossier.business.name,
                        dossier.business.phone,
                        dossier.business.address,
                    ]
                )
            )
            or len(dossier.jobs) > 0
            or len(dossier.coworkers) > 0
            or (
                dossier.github is not None
                and (
                    dossier.github.get("publicCommits", 0) > 0
                    or len(dossier.github.get("organizations", [])) > 0
                )
            )
        )

        # #region agent log
        logger.info(
            f"[DEBUG-85dffc] job status determination: has_real_data={has_real_data} has_photo={dossier.photo is not None} handle_count={len(dossier.handles)} email_count={len(dossier.emails)} source_count={len(dossier.sources)} job_count={len(dossier.jobs)}"
        )
        # #endregion

        status = JobStatus.completed if has_real_data else JobStatus.completed_no_data
        return await self.jobs.mark_status(
            job,
            status,
            dossier_payload=dossier.model_dump(mode="json"),
        )

    async def get_job(self, job_id: str) -> JobRecord | None:
        return await self.jobs.get(job_id)

    async def list_jobs(
        self, limit: int, offset: int, user_id: UUID | None = None
    ) -> tuple[list[JobRecord], int]:
        return await self.jobs.list(limit, offset, user_id=user_id)

    @staticmethod
    def identifier_summary_from_payload(payload: dict[str, Any] | None) -> str:
        if not payload:
            return ""
        values = [
            payload.get("email"),
            payload.get("linkedin_url"),
            payload.get("linkedinUrl"),
            payload.get("username"),
            payload.get("company"),
            payload.get("business"),
            payload.get("job_search"),
            payload.get("jobSearch"),
        ]
        return " • ".join(str(v) for v in values if isinstance(v, str) and v)

    async def register_opt_out(self, identifier: str, reason: str | None = None) -> PurgeResult:
        identifier_hash = hash_identifier(identifier)
        await add_suppression(self.db, identifier, reason)
        await log_event(
            self.db, AuditEventType.opt_out, identifier_hash, details={"reason": reason or ""}
        )

        try:
            purge_result = await purge_identifier_data(self.db, identifier)
        except Exception:
            logger.warning(
                "purge failed for identifier_hash=%s", identifier_hash[:12], exc_info=True
            )
            purge_result = PurgeResult()
            await self.db.commit()

        await log_event(
            self.db,
            AuditEventType.data_purged,
            identifier_hash,
            details={
                "jobs_cleared": purge_result.jobs_cleared,
                "photos_deleted": purge_result.photos_deleted,
                "r2_objects_deleted": purge_result.r2_objects_deleted,
            },
        )
        await self.db.commit()
        return purge_result

    async def add_suppression(self, identifier: str, reason: str | None = None) -> None:
        await add_suppression(self.db, identifier, reason)

    async def check_suppression(self, identifier: str) -> bool:
        return await check_suppression(self.db, identifier)

    async def _dispatch(
        self,
        request: EnrichmentRequest,
        *,
        sync_mode: bool = False,
    ) -> list[dict[str, Any]]:
        tiers = list(request.requested_tiers) or list(RequestedTier)
        if sync_mode:
            tiers = [tier for tier in tiers if tier != RequestedTier.tier1]

        # Build tier tasks for parallel execution
        tier_tasks = []
        tier_metadata = []

        if RequestedTier.tier1 in tiers:
            tier_tasks.append(self._run_tier1_task(request))
            tier_metadata.append(("tier1", RequestedTier.tier1))

        if RequestedTier.tier2 in tiers:
            tier_tasks.append(self._run_tier2_task(request))
            tier_metadata.append(("tier2", RequestedTier.tier2))

        if RequestedTier.tier3 in tiers:
            tier_tasks.append(self._run_tier3_task(request))
            tier_metadata.append(("tier3", RequestedTier.tier3))

        if RequestedTier.tier4 in tiers:
            tier_tasks.append(self._run_tier4_task(request))
            tier_metadata.append(("tier4", RequestedTier.tier4))

        # Execute all tiers in parallel
        tier_results = await asyncio.gather(*tier_tasks, return_exceptions=True)

        # Process results with error handling
        payloads = []
        failed_tiers = []
        tier_timings = {}

        for (tier_name, tier_enum), result in zip(tier_metadata, tier_results):
            if isinstance(result, BaseException):
                logger.error(
                    f"{tier_name} failed during parallel execution",
                    exc_info=result,
                    extra={
                        "tier": tier_name,
                        "error_type": type(result).__name__,
                    },
                )
                failed_tiers.append(tier_name)
            elif isinstance(result, dict):
                # Result includes payloads and metadata
                payloads.extend(result.get("payloads", []))
                tier_timings[tier_name] = result.get("duration", 0)

        # Add execution metadata to first payload or create metadata payload
        if payloads:
            if not payloads[0].get("metadata"):
                payloads[0]["metadata"] = {}
            payloads[0]["metadata"]["tier_execution"] = {
                "parallel": True,
                "timings": tier_timings,
                "failed_tiers": failed_tiers,
            }

        return payloads

    async def _run_tier1_task(self, request: EnrichmentRequest) -> dict[str, Any]:
        """Tier 1: LinkedIn photo (serial execution)"""
        import time

        from app.observability.tier_metrics import track_tier_execution

        async with track_tier_execution("tier1"):
            start = time.time()
            logger.info(
                "Starting tier1 execution",
                extra={
                    "tier": "tier1",
                    "job_id": getattr(request, "job_id", None),
                    "parallel_mode": True,
                },
            )
            try:
                payloads = await self._run_tier(self.tier1, request)
                duration = time.time() - start
                # #region agent log
                logger.info(
                    "[DEBUG-85dffc] tier1 task completed",
                    extra={
                        "payload_count": len(payloads),
                        "empty_payloads": sum(1 for p in payloads if not p or p == {}),
                        "duration": duration,
                        "hypothesisId": "B,D",
                    },
                )
                # #endregion
                logger.info(
                    "Completed tier1 execution",
                    extra={
                        "tier": "tier1",
                        "duration_seconds": duration,
                        "success": True,
                        "enricher_count": len(payloads),
                    },
                )
                return {"payloads": payloads, "duration": duration}
            except Exception:
                logger.exception("Tier 1 task failed")
                raise

    async def _run_tier2_task(self, request: EnrichmentRequest) -> dict[str, Any]:
        """Tier 2: Social handles (Sherlock, Maigret, SocialAnalyzer in parallel)"""
        import time

        from app.observability.tier_metrics import track_tier_execution

        async with track_tier_execution("tier2"):
            start = time.time()
            logger.info(
                "Starting tier2 execution",
                extra={
                    "tier": "tier2",
                    "job_id": getattr(request, "job_id", None),
                    "parallel_mode": True,
                },
            )
            try:
                payloads = await self._run_tier_parallel(self.tier2, request)
                duration = time.time() - start
                logger.info(
                    "Completed tier2 execution",
                    extra={
                        "tier": "tier2",
                        "duration_seconds": duration,
                        "success": True,
                        "enricher_count": len(payloads),
                    },
                )
                return {"payloads": payloads, "duration": duration}
            except Exception:
                logger.exception("Tier 2 task failed")
                raise

    async def _run_tier3_task(self, request: EnrichmentRequest) -> dict[str, Any]:
        """Tier 3: Email discovery + verification"""
        import time

        from app.observability.tier_metrics import track_tier_execution

        async with track_tier_execution("tier3"):
            start = time.time()
            logger.info(
                "Starting tier3 execution",
                extra={
                    "tier": "tier3",
                    "job_id": getattr(request, "job_id", None),
                    "parallel_mode": True,
                },
            )
            try:
                # Discovery phase (parallel)
                discover_payloads = await self._run_tier_parallel(self.tier3_discover, request)

                # Verification phase (sequential batch)
                candidates = self._collect_email_candidates(request, discover_payloads)
                if candidates:
                    verify_payload = await self._verify_email_batch(candidates)
                    if verify_payload:
                        discover_payloads.append(verify_payload)

                duration = time.time() - start
                logger.info(
                    "Completed tier3 execution",
                    extra={
                        "tier": "tier3",
                        "duration_seconds": duration,
                        "success": True,
                        "enricher_count": len(discover_payloads),
                        "emails_verified": len(candidates) if candidates else 0,
                    },
                )
                return {"payloads": discover_payloads, "duration": duration}
            except Exception:
                logger.exception("Tier 3 task failed")
                raise

    async def _run_tier4_task(self, request: EnrichmentRequest) -> dict[str, Any]:
        """Tier 4: Jobs + local business (JobSpy, GMaps in parallel)"""
        import time

        from app.observability.tier_metrics import track_tier_execution

        async with track_tier_execution("tier4"):
            start = time.time()
            logger.info(
                "Starting tier4 execution",
                extra={
                    "tier": "tier4",
                    "job_id": getattr(request, "job_id", None),
                    "parallel_mode": True,
                },
            )
            try:
                payloads = await self._run_tier_parallel(self.tier4, request)
                duration = time.time() - start
                logger.info(
                    "Completed tier4 execution",
                    extra={
                        "tier": "tier4",
                        "duration_seconds": duration,
                        "success": True,
                        "enricher_count": len(payloads),
                    },
                )
                return {"payloads": payloads, "duration": duration}
            except Exception:
                logger.exception("Tier 4 task failed")
                raise

    async def _run_tier(
        self, enrichers: list[Enricher], request: EnrichmentRequest
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for enricher in enrichers:
            results.append(await self._invoke_enricher(enricher, request))
        return results

    async def _run_tier_parallel(
        self,
        enrichers: list[Enricher],
        request: EnrichmentRequest,
    ) -> list[dict[str, Any]]:
        results = await asyncio.gather(
            *(self._invoke_enricher_with_retry(enricher, request) for enricher in enrichers),
            return_exceptions=True,
        )
        payloads: list[dict[str, Any]] = []
        exception_count = 0
        for result in results:
            if isinstance(result, BaseException):
                logger.exception("parallel enricher failed", exc_info=result)
                exception_count += 1
                payloads.append({})
            else:
                payloads.append(result)
        # #region agent log
        logger.info(
            "[DEBUG-85dffc] _run_tier_parallel completed",
            extra={
                "total_enrichers": len(enrichers),
                "exception_count": exception_count,
                "total_payloads": len(payloads),
                "empty_payloads": sum(1 for p in payloads if not p or p == {}),
                "hypothesisId": "B",
            },
        )
        # #endregion
        return payloads

    async def _invoke_enricher_with_retry(
        self, enricher: Enricher, request: EnrichmentRequest
    ) -> dict[str, Any]:
        """Invoke enricher with exponential backoff retry for transient failures"""
        settings = get_settings()
        max_retries = settings.enricher_max_retries
        backoff = settings.enricher_retry_backoff

        for attempt in range(max_retries):
            try:
                return await self._invoke_enricher(enricher, request)

            except (TimeoutError, ConnectionError, OSError) as e:
                # Transient network errors - retry
                if attempt < max_retries - 1:
                    wait_time = backoff**attempt
                    logger.warning(
                        f"Enricher {enricher.source_name} transient failure "
                        f"(attempt {attempt + 1}/{max_retries}), "
                        f"retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(
                        f"Enricher {enricher.source_name} failed after {max_retries} attempts"
                    )
                    return {}

            except Exception as e:
                # Non-transient errors - fail immediately
                logger.exception(
                    f"Enricher {enricher.source_name} permanent failure: {type(e).__name__}"
                )
                return {}

        return {}

    async def _invoke_enricher(
        self, worker: Enricher, request: EnrichmentRequest
    ) -> dict[str, Any]:
        # #region agent log
        logger.info(
            "[DEBUG-85dffc] _invoke_enricher entry",
            extra={
                "enricher_name": getattr(worker, "source_name", type(worker).__name__),
                "has_validate": hasattr(worker, "validate"),
                "hypothesisId": "A",
            },
        )
        # #endregion
        try:
            if not await worker.validate(request):
                # #region agent log
                logger.info(
                    "[DEBUG-85dffc] enricher validation failed",
                    extra={
                        "enricher_name": getattr(worker, "source_name", type(worker).__name__),
                        "hypothesisId": "A",
                    },
                )
                # #endregion
                return {}
            await worker.initialize()
            try:
                payload = await worker.run(request)
                payload = await worker.normalize(payload)
                result = await worker.score(payload)
                # #region agent log
                logger.info(
                    f"[DEBUG-85dffc] enricher completed successfully: enricher={getattr(worker, 'source_name', type(worker).__name__)} payload_keys={list(result.keys()) if isinstance(result, dict) else None} is_empty={not result or result == {}} has_photo={'photo' in result if isinstance(result, dict) else False}"
                )
                # #endregion
                return result
            finally:
                await worker.cleanup()
        except Exception as exc:
            # #region agent log
            logger.info(
                "[DEBUG-85dffc] enricher exception caught",
                extra={
                    "enricher_name": getattr(worker, "source_name", type(worker).__name__),
                    "exception_type": type(exc).__name__,
                    "exception_msg": str(exc)[:200],
                    "hypothesisId": "A",
                },
            )
            # #endregion
            logger.exception(
                "enricher failed: %s",
                getattr(worker, "source_name", type(worker).__name__),
            )
            try:
                await worker.cleanup()
            except Exception:
                pass
            return {}

    @staticmethod
    def _collect_email_candidates(
        request: EnrichmentRequest,
        discover_payloads: list[dict[str, Any]],
    ) -> list[str]:
        settings = get_settings()
        seen: set[str] = set()
        candidates: list[str] = []

        def add(raw: str) -> None:
            normalized = raw.strip().lower()
            if not normalized or "@" not in normalized or normalized in seen:
                return
            seen.add(normalized)
            candidates.append(normalized)

        if request.email:
            add(request.email)

        for payload in discover_payloads:
            emails = payload.get("emails")
            if not isinstance(emails, list):
                continue
            for email in emails:
                add(str(email))

        if not candidates and request.username:
            for pattern in common_email_patterns(request.username, slugify_domain(request.company)):
                add(pattern)

        cap = max(1, settings.email_verify_max_per_job)
        return candidates[:cap]

    async def _verify_email_batch(self, candidates: list[str]) -> dict[str, Any]:
        payload = await self._email_verify.verify_emails(candidates)
        if not payload:
            return {}
        payload.setdefault("sources", [self._email_verify.source_name])
        return payload

    async def _merge(self, request: EnrichmentRequest, payloads: list[dict[str, Any]]) -> Dossier:
        dossier = merge_payloads(request, payloads)
        dossier.handles, dropped = await disambiguate_handles(
            request, dossier.handles, llm=self.llm
        )
        if dropped:
            dossier.metadata["disambiguation_dropped"] = dropped
        dossier.confidence = build_confidence(request, dossier)
        return dossier

    # Compat aliases used by older tests that call private helpers on the orchestrator
    async def _disambiguate_handles(
        self, request: EnrichmentRequest, handles: list[SocialHandle]
    ) -> tuple[list[SocialHandle], int]:
        return await disambiguate_handles(request, handles, llm=self.llm)

    def _base_dossier(self, request: EnrichmentRequest) -> Dossier:
        return base_dossier(request)

    @staticmethod
    def _normalize_job_key(title: str, company: str, location: str) -> str:
        from app.enrichers.merge import normalize_job_key

        return normalize_job_key(title, company, location)

    @staticmethod
    def _job_location_specificity(location: str) -> int:
        from app.enrichers.merge import job_location_specificity

        return job_location_specificity(location)

    async def _build_confidence(
        self, request: EnrichmentRequest, dossier: Dossier
    ) -> list[ConfidenceBreakdown]:
        return build_confidence(request, dossier)

    async def _is_suppressed(self, request: EnrichmentRequest) -> bool:
        return await is_request_suppressed(self.db, request)
