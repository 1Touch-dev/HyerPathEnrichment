"""Enrichment execution engine — sole owner of run / dispatch / merge orchestration."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.audit import log_event
from app.compliance.identifiers import hash_identifier, hashes_from_request
from app.compliance.purge import PurgeResult, purge_identifier_data
from app.compliance.suppression import (
    add_suppression,
    check_suppression,
    is_request_suppressed,
)
from app.config import get_settings
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
from app.clients.llm import LiteLLMDisambiguator
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

    async def run(self, request: EnrichmentRequest) -> JobRecord:
        """Synchronous path: create a job and run the pipeline inline."""
        job = await self.jobs.create(request, JobStatus.running)
        await self.jobs.flush()
        return await self._execute(job, request, sync_mode=True)

    async def create_queued_job(self, request: EnrichmentRequest) -> JobRecord:
        """Async path: persist a queued job for a worker to pick up later."""
        if await is_request_suppressed(self.db, request):
            return await self._create_suppressed_job(request)

        job = await self.jobs.create(request, JobStatus.queued)
        await self.jobs.commit()
        await self.jobs.refresh(job)
        return job

    async def is_request_suppressed(self, request: EnrichmentRequest) -> bool:
        return await is_request_suppressed(self.db, request)

    async def create_suppressed_job(self, request: EnrichmentRequest) -> JobRecord:
        return await self._create_suppressed_job(request)

    async def _create_suppressed_job(self, request: EnrichmentRequest) -> JobRecord:
        job = await self.jobs.create(request, JobStatus.suppressed)
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
        return job

    async def execute_job(self, job_id: str) -> JobRecord | None:
        """Worker path: load a queued job by id and run the pipeline."""
        job = await self.jobs.get(job_id)
        if job is None:
            logger.warning("execute_job called for unknown job")
            return None
        request = EnrichmentRequest.model_validate(job.request_payload)
        job.status = JobStatus.running.value
        try:
            return await self._execute(job, request, sync_mode=False)
        except Exception:
            await self.jobs.rollback()
            failed = await self.jobs.get(job_id)
            if failed is not None:
                await self.jobs.mark_status(failed, JobStatus.failed)
            raise

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
        dossier = await self._merge(request, payloads)
        return await self.jobs.mark_status(
            job,
            JobStatus.completed,
            dossier_payload=dossier.model_dump(mode="json"),
        )

    async def get_job(self, job_id: str) -> JobRecord | None:
        return await self.jobs.get(job_id)

    async def list_jobs(self, limit: int, offset: int) -> tuple[list[JobRecord], int]:
        return await self.jobs.list(limit, offset)

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
        await log_event(self.db, AuditEventType.opt_out, identifier_hash, details={"reason": reason or ""})

        try:
            purge_result = await purge_identifier_data(self.db, identifier)
        except Exception:
            logger.warning("purge failed for identifier_hash=%s", identifier_hash[:12], exc_info=True)
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

        payloads: list[dict[str, Any]] = []
        if RequestedTier.tier1 in tiers:
            payloads.extend(await self._run_tier(self.tier1, request))
        if RequestedTier.tier2 in tiers:
            payloads.extend(await self._run_tier_parallel(self.tier2, request))
        if RequestedTier.tier3 in tiers:
            discover_payloads = await self._run_tier_parallel(self.tier3_discover, request)
            payloads.extend(discover_payloads)
            candidates = self._collect_email_candidates(request, discover_payloads)
            if candidates:
                verify_payload = await self._verify_email_batch(candidates)
                if verify_payload:
                    payloads.append(verify_payload)
        if RequestedTier.tier4 in tiers:
            payloads.extend(await self._run_tier_parallel(self.tier4, request))
        return payloads

    async def _run_tier(self, enrichers: list[Enricher], request: EnrichmentRequest) -> list[dict[str, Any]]:
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
            *(self._invoke_enricher(enricher, request) for enricher in enrichers),
            return_exceptions=True,
        )
        payloads: list[dict[str, Any]] = []
        for result in results:
            if isinstance(result, BaseException):
                logger.exception("parallel enricher failed", exc_info=result)
                payloads.append({})
            else:
                payloads.append(result)
        return payloads

    async def _invoke_enricher(self, worker: Enricher, request: EnrichmentRequest) -> dict[str, Any]:
        try:
            if not await worker.validate(request):
                return {}
            await worker.initialize()
            try:
                payload = await worker.run(request)
                payload = await worker.normalize(payload)
                return await worker.score(payload)
            finally:
                await worker.cleanup()
        except Exception:
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

    async def _merge(self, request: EnrichmentRequest, payloads: list[dict[str, Any]]):
        dossier = merge_payloads(request, payloads)
        dossier.handles, dropped = await disambiguate_handles(
            request, dossier.handles, llm=self.llm
        )
        if dropped:
            dossier.metadata["disambiguation_dropped"] = dropped
        dossier.confidence = build_confidence(request, dossier)
        return dossier

    # Compat aliases used by older tests that call private helpers on the orchestrator
    async def _disambiguate_handles(self, request: EnrichmentRequest, handles):
        return await disambiguate_handles(request, handles, llm=self.llm)

    def _base_dossier(self, request: EnrichmentRequest):
        return base_dossier(request)

    @staticmethod
    def _normalize_job_key(title: str, company: str, location: str) -> str:
        from app.enrichers.merge import normalize_job_key

        return normalize_job_key(title, company, location)

    @staticmethod
    def _job_location_specificity(location: str) -> int:
        from app.enrichers.merge import job_location_specificity

        return job_location_specificity(location)

    async def _build_confidence(self, request: EnrichmentRequest, dossier):
        return build_confidence(request, dossier)

    async def _is_suppressed(self, request: EnrichmentRequest) -> bool:
        return await is_request_suppressed(self.db, request)
