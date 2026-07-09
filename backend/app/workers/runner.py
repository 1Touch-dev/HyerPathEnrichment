from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from redis.exceptions import RedisError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enrichers import (
    CrossLinkedEnricher,
    EmailDiscoverEnricher,
    EmailVerifyEnricher,
    GitReconEnricher,
    JobSpyEnricher,
    LinkedInPhotoEnricher,
    LocalBusinessEnricher,
    MaigretEnricher,
    SherlockEnricher,
    SocialAnalyzerEnricher,
    TheHarvesterEnricher,
)
from app.enrichers.base import Enricher
from app.llm_router import LiteLLMDisambiguator
from app.models import ConfidenceBreakdown, Dossier, EnrichmentRequest, JobRecord, JobListing, JobStatus, PhotoAsset, RequestedTier, SocialHandle, SuppressionRecord, VerifiedEmail, BusinessProfile
from app.storage.redis_client import get_redis_client

logger = logging.getLogger(__name__)

SUPPRESSION_SET_KEY = "suppression:hashes"


class PipelineOrchestrator:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = LiteLLMDisambiguator()
        self.tier1: list[Enricher] = [LinkedInPhotoEnricher()]
        self.tier2: list[Enricher] = [SherlockEnricher(), MaigretEnricher(), SocialAnalyzerEnricher()]
        self.tier3: list[Enricher] = [GitReconEnricher(), TheHarvesterEnricher(), EmailDiscoverEnricher(), EmailVerifyEnricher(), CrossLinkedEnricher()]
        self.tier4: list[Enricher] = [JobSpyEnricher(), LocalBusinessEnricher()]

    async def run(self, request: EnrichmentRequest) -> JobRecord:
        """Synchronous path: create a job and run the pipeline inline."""
        job = await self._create_job(request, JobStatus.running)
        await self.db.flush()
        return await self._execute(job, request, sync_mode=True)

    async def create_queued_job(self, request: EnrichmentRequest) -> JobRecord:
        """Async path: persist a queued job for a worker to pick up later."""
        job = await self._create_job(request, JobStatus.queued)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def execute_job(self, job_id: str) -> JobRecord | None:
        """Worker path: load a queued job by id and run the pipeline."""
        job = await self.get_job(job_id)
        if job is None:
            logger.warning("execute_job called for unknown job")
            return None
        request = EnrichmentRequest.model_validate(job.request_payload)
        job.status = JobStatus.running.value
        try:
            return await self._execute(job, request, sync_mode=False)
        except Exception:
            await self.db.rollback()
            failed = await self.db.get(JobRecord, job_id)
            if failed is not None:
                failed.status = JobStatus.failed.value
                failed.updated_at = datetime.now(timezone.utc)
                await self.db.commit()
            raise

    async def _create_job(self, request: EnrichmentRequest, status: JobStatus) -> JobRecord:
        job = JobRecord(
            id=f"job_{uuid4().hex}",
            status=status.value,
            request_payload=request.model_dump(mode="json"),
            dossier_payload={},
        )
        self.db.add(job)
        return job

    async def _execute(
        self,
        job: JobRecord,
        request: EnrichmentRequest,
        *,
        sync_mode: bool = False,
    ) -> JobRecord:
        if await self._is_suppressed(request):
            dossier = self._base_dossier(request)
            dossier.metadata["suppressed"] = True
            job.status = JobStatus.suppressed.value
            job.dossier_payload = dossier.model_dump(mode="json")
            job.updated_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(job)
            return job

        payloads = await self._dispatch(request, sync_mode=sync_mode)
        dossier = await self._merge(request, payloads)
        job.status = JobStatus.completed.value
        job.dossier_payload = dossier.model_dump(mode="json")
        job.updated_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_job(self, job_id: str) -> JobRecord | None:
        return await self.db.get(JobRecord, job_id)

    async def add_suppression(self, identifier: str, reason: str | None = None) -> None:
        identifier_hash = self._hash(identifier)
        record = SuppressionRecord(identifier_hash=identifier_hash, reason=reason or "")
        await self.db.merge(record)
        await self.db.commit()
        try:
            await get_redis_client().sadd(SUPPRESSION_SET_KEY, identifier_hash)
        except RedisError:
            # SQL is the durable record; reads fall back to SQL on Redis miss.
            logger.warning("redis unavailable during add_suppression; SQL record persisted")

    async def check_suppression(self, identifier: str) -> bool:
        identifier_hash = self._hash(identifier)
        try:
            if await get_redis_client().sismember(SUPPRESSION_SET_KEY, identifier_hash):
                return True
        except RedisError:
            logger.warning("redis unavailable during check_suppression; falling back to SQL")
        statement = select(SuppressionRecord).where(SuppressionRecord.identifier_hash == identifier_hash)
        result = await self.db.execute(statement)
        suppressed = result.scalar_one_or_none() is not None
        if suppressed:
            try:
                await get_redis_client().sadd(SUPPRESSION_SET_KEY, identifier_hash)
            except RedisError:
                pass
        return suppressed

    async def _is_suppressed(self, request: EnrichmentRequest) -> bool:
        identifiers = [request.email, request.linkedin_url, request.username, request.company, request.business, request.job_search]
        for identifier in [value for value in identifiers if value]:
            if await self.check_suppression(identifier):
                return True
        return False

    async def _dispatch(
        self,
        request: EnrichmentRequest,
        *,
        sync_mode: bool = False,
    ) -> list[dict[str, Any]]:
        tiers = list(request.requested_tiers)
        if sync_mode:
            tiers = [tier for tier in tiers if tier != RequestedTier.tier1]

        payloads: list[dict[str, Any]] = []
        if RequestedTier.tier1 in tiers:
            payloads.extend(await self._run_tier(self.tier1, request))
        if RequestedTier.tier2 in tiers:
            payloads.extend(await self._run_tier_parallel(self.tier2, request))
        if RequestedTier.tier3 in tiers:
            payloads.extend(await self._run_tier_parallel(self.tier3, request))
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
        return list(await asyncio.gather(*(self._invoke_enricher(enricher, request) for enricher in enrichers)))

    async def _invoke_enricher(self, worker: Enricher, request: EnrichmentRequest) -> dict[str, Any]:
        if not await worker.validate(request):
            return {}
        await worker.initialize()
        try:
            payload = await worker.run(request)
            payload = await worker.normalize(payload)
            return await worker.score(payload)
        finally:
            await worker.cleanup()

    async def _merge(self, request: EnrichmentRequest, payloads: list[dict[str, Any]]) -> Dossier:
        dossier = self._base_dossier(request)
        handles_seen: set[tuple[str, str]] = set()
        emails_seen: set[str] = set()
        sources: set[str] = set()

        for payload in payloads:
            photo = payload.get("photo")
            if isinstance(photo, dict) and dossier.photo is None:
                dossier.photo = PhotoAsset.model_validate(photo)

            handles = payload.get("handles")
            if isinstance(handles, list):
                for handle in handles:
                    if not isinstance(handle, dict):
                        continue
                    key = (str(handle.get("platform", "")).lower(), str(handle.get("username", "")).lower())
                    if key not in handles_seen:
                        handles_seen.add(key)
                        dossier.handles.append(SocialHandle.model_validate(handle))

            emails = payload.get("emails")
            if isinstance(emails, list):
                for email in emails:
                    normalized = str(email).lower()
                    if normalized not in emails_seen:
                        emails_seen.add(normalized)
                        dossier.emails.append(str(email))

            verified_emails = payload.get("verified_emails")
            if isinstance(verified_emails, list):
                for verified in verified_emails:
                    if not isinstance(verified, dict):
                        continue
                    candidate = VerifiedEmail.model_validate(verified)
                    if candidate.value.lower() not in {item.value.lower() for item in dossier.verified_emails}:
                        dossier.verified_emails.append(candidate)

            github = payload.get("github")
            if isinstance(github, dict):
                dossier.github = github

            coworkers = payload.get("coworkers")
            if isinstance(coworkers, list):
                for coworker in coworkers:
                    value = str(coworker)
                    if value not in dossier.coworkers:
                        dossier.coworkers.append(value)

            jobs = payload.get("jobs")
            if isinstance(jobs, list):
                for job in jobs:
                    if not isinstance(job, dict):
                        continue
                    job_candidate = JobListing.model_validate(job)
                    if job_candidate.model_dump(mode="json") not in [existing.model_dump(mode="json") for existing in dossier.jobs]:
                        dossier.jobs.append(job_candidate)

            business = payload.get("business")
            if isinstance(business, dict) and dossier.business is None:
                dossier.business = BusinessProfile.model_validate(business)

            raw_sources = payload.get("sources")
            if isinstance(raw_sources, list):
                for source in raw_sources:
                    sources.add(str(source))

        dossier.sources = sorted(sources)
        dossier.confidence = await self._build_confidence(request, dossier)
        return dossier

    async def _build_confidence(self, request: EnrichmentRequest, dossier: Dossier) -> list[ConfidenceBreakdown]:
        username = request.username or (request.email or "candidate@example.com").split("@")[0]
        handle_match = any(handle.username.lower() == username.lower() for handle in dossier.handles)
        decision = await self.llm.compare(username, username if handle_match else "unknown")
        return [
            ConfidenceBreakdown(
                label="identity-match",
                score=0.91 if handle_match else 0.44,
                evidence=[
                    f"cross-source handles: {len(dossier.handles)}",
                    f"llm confirmation: {decision.same_identity} ({decision.reason})",
                ],
            ),
            ConfidenceBreakdown(
                label="email-verification",
                score=0.89 if dossier.verified_emails else 0.22,
                evidence=[f"verified emails: {len(dossier.verified_emails)}"],
            ),
            ConfidenceBreakdown(
                label="coverage",
                score=min(1.0, 0.2 + (len(dossier.sources) * 0.1)),
                evidence=[f"sources: {', '.join(dossier.sources) or 'none'}"],
            ),
        ]

    def _base_dossier(self, request: EnrichmentRequest) -> Dossier:
        values = [request.email, request.linkedin_url, request.username, request.company, request.business, request.job_search]
        return Dossier(
            metadata={
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "pipeline_id": f"pipe_{uuid4().hex}",
                "requested_tiers": [tier.value for tier in request.requested_tiers],
                "identifier_summary": " • ".join([value for value in values if value]),
            }
        )

    def _hash(self, identifier: str) -> str:
        return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()
