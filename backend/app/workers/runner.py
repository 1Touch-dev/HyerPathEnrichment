from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.audit import log_event
from app.compliance.identifiers import hash_identifier, hashes_from_request, request_identifier_values
from app.compliance.purge import PurgeResult, purge_identifier_data
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
from app.config import get_settings
from app.enrichers._shared import common_email_patterns, slugify_domain
from app.enrichers.base import Enricher
from app.llm_router import LiteLLMDisambiguator
from app.models import (
    AuditEventType,
    ConfidenceBreakdown,
    Dossier,
    EnrichmentRequest,
    JobRecord,
    JobListing,
    JobStatus,
    PhotoAsset,
    RequestedTier,
    SocialHandle,
    SuppressionRecord,
    VerifiedEmail,
    BusinessProfile,
)
from app.storage.redis_client import get_redis_client

logger = logging.getLogger(__name__)

_COMPANY_SUFFIXES = re.compile(
    r"\b(inc\.?|llc\.?|l\.?l\.?c\.?|corp\.?|corporation|ltd\.?|limited|co\.?)\s*$",
    re.IGNORECASE,
)

SUPPRESSION_SET_KEY = "suppression:hashes"


class PipelineOrchestrator:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = LiteLLMDisambiguator()
        self.tier1: list[Enricher] = [LinkedInPhotoEnricher()]
        self.tier2: list[Enricher] = [SherlockEnricher(), MaigretEnricher(), SocialAnalyzerEnricher()]
        self.tier3_discover: list[Enricher] = [
            GitReconEnricher(),
            TheHarvesterEnricher(),
            EmailDiscoverEnricher(),
            CrossLinkedEnricher(),
        ]
        self._email_verify = EmailVerifyEnricher()
        self.tier4: list[Enricher] = [JobSpyEnricher(), LocalBusinessEnricher()]

    async def run(self, request: EnrichmentRequest) -> JobRecord:
        """Synchronous path: create a job and run the pipeline inline."""
        job = await self._create_job(request, JobStatus.running)
        await self.db.flush()
        return await self._execute(job, request, sync_mode=True)

    async def create_queued_job(self, request: EnrichmentRequest) -> JobRecord:
        """Async path: persist a queued job for a worker to pick up later."""
        if await self.is_request_suppressed(request):
            return await self._create_suppressed_job(request)

        job = await self._create_job(request, JobStatus.queued)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def is_request_suppressed(self, request: EnrichmentRequest) -> bool:
        """Public wrapper used by routes before enqueueing."""
        return await self._is_suppressed(request)

    async def create_suppressed_job(self, request: EnrichmentRequest) -> JobRecord:
        """Create a suppressed job without running enrichers (async pre-check path)."""
        return await self._create_suppressed_job(request)

    async def _create_suppressed_job(self, request: EnrichmentRequest) -> JobRecord:
        job = await self._create_job(request, JobStatus.suppressed)
        dossier = self._base_dossier(request)
        dossier.metadata["suppressed"] = True
        job.dossier_payload = dossier.model_dump(mode="json")
        job.updated_at = datetime.now(timezone.utc)

        request_hashes = hashes_from_request(request)
        if request_hashes:
            await log_event(
                self.db,
                AuditEventType.enrichment_suppressed,
                request_hashes[0],
                job_id=job.id,
            )

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
            identifier_hashes=hashes_from_request(request),
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

    async def list_jobs(self, limit: int, offset: int) -> tuple[list[JobRecord], int]:
        """Return paginated jobs ordered by created_at descending."""
        clamped_limit = max(1, min(limit, 100))
        clamped_offset = max(0, offset)

        total_result = await self.db.execute(select(func.count()).select_from(JobRecord))
        total = int(total_result.scalar_one())

        statement = (
            select(JobRecord)
            .order_by(JobRecord.created_at.desc())
            .limit(clamped_limit)
            .offset(clamped_offset)
        )
        result = await self.db.execute(statement)
        return list(result.scalars().all()), total

    @staticmethod
    def identifier_summary_from_payload(payload: dict[str, Any] | None) -> str:
        """Mirror frontend identifierSummaryFromPayload in api-adapter.ts."""
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
        """Register suppression, audit the event, and purge stored data for the identifier."""
        identifier_hash = hash_identifier(identifier)
        await self.add_suppression(identifier, reason)
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
        identifier_hash = hash_identifier(identifier)
        record = SuppressionRecord(identifier_hash=identifier_hash, reason=reason or "")
        await self.db.merge(record)
        await self.db.commit()
        try:
            await get_redis_client().sadd(SUPPRESSION_SET_KEY, identifier_hash)
        except RedisError:
            # SQL is the durable record; reads fall back to SQL on Redis miss.
            logger.warning("redis unavailable during add_suppression; SQL record persisted")

    async def check_suppression(self, identifier: str) -> bool:
        identifier_hash = hash_identifier(identifier)
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
        for identifier in request_identifier_values(request):
            if await self.check_suppression(identifier):
                return True
        return False

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

    async def _merge(self, request: EnrichmentRequest, payloads: list[dict[str, Any]]) -> Dossier:
        dossier = self._base_dossier(request)
        handles_seen: set[tuple[str, str]] = set()
        emails_seen: set[str] = set()
        jobs_seen: dict[str, int] = {}
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
                    candidate = SocialHandle.model_validate(handle)
                    if key not in handles_seen:
                        handles_seen.add(key)
                        dossier.handles.append(candidate)
                        continue
                    # Prefer higher confidence on platform/username collision.
                    for index, existing in enumerate(dossier.handles):
                        existing_key = (existing.platform.lower(), existing.username.lower())
                        if existing_key != key:
                            continue
                        if candidate.confidence > existing.confidence:
                            dossier.handles[index] = candidate
                        break

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
                    key = self._normalize_job_key(
                        job_candidate.title,
                        job_candidate.company,
                        job_candidate.location,
                    )
                    if key not in jobs_seen:
                        jobs_seen[key] = len(dossier.jobs)
                        dossier.jobs.append(job_candidate)
                        continue
                    existing_idx = jobs_seen[key]
                    existing = dossier.jobs[existing_idx]
                    if self._job_location_specificity(job_candidate.location) > self._job_location_specificity(
                        existing.location
                    ):
                        dossier.jobs[existing_idx] = job_candidate

            business = payload.get("business")
            if isinstance(business, dict) and dossier.business is None:
                dossier.business = BusinessProfile.model_validate(business)

            raw_sources = payload.get("sources")
            if isinstance(raw_sources, list):
                for source in raw_sources:
                    sources.add(str(source))

        dossier.sources = sorted(sources)
        dossier.handles, dropped = await self._disambiguate_handles(request, dossier.handles)
        if dropped:
            dossier.metadata["disambiguation_dropped"] = dropped
        dossier.confidence = await self._build_confidence(request, dossier)
        return dossier

    async def _disambiguate_handles(
        self, request: EnrichmentRequest, handles: list[SocialHandle]
    ) -> tuple[list[SocialHandle], int]:
        """Keep high-confidence handles; LLM-gate the rest against DISAMBIGUATION_THRESHOLD."""
        threshold = get_settings().disambiguation_threshold
        target = self._target_identity(request)
        kept: list[SocialHandle] = []
        dropped = 0

        for handle in handles:
            if handle.confidence >= threshold:
                kept.append(handle)
                continue

            evidence = f"{handle.platform} | {handle.username} | {handle.profile_url}"
            decision = await self.llm.compare(target, evidence)
            if decision.same_identity and decision.confidence >= threshold:
                handle.confidence = max(handle.confidence, decision.confidence)
                kept.append(handle)
            else:
                dropped += 1
                logger.info(
                    "dropped ambiguous handle %s/%s (same=%s llm_conf=%.2f)",
                    handle.platform,
                    handle.username,
                    decision.same_identity,
                    decision.confidence,
                )

        return kept, dropped

    @staticmethod
    def _normalize_job_key(title: str, company: str, location: str) -> str:
        def norm(text: str) -> str:
            cleaned = re.sub(r"[^\w\s]", " ", text.lower())
            return re.sub(r"\s+", " ", cleaned).strip()

        company_norm = _COMPANY_SUFFIXES.sub("", norm(company)).strip()
        return f"{norm(title)}|{company_norm}|{norm(location)}"

    @staticmethod
    def _job_location_specificity(location: str) -> int:
        loc = location.strip().lower()
        if not loc or loc in {"remote", "anywhere"}:
            return 0
        return len(loc.split(",")) + len(loc.split())

    @staticmethod
    def _target_identity(request: EnrichmentRequest) -> str:
        parts = [
            request.username,
            request.email,
            request.linkedin_url,
            request.company,
        ]
        return " | ".join(part for part in parts if part) or "unknown"

    async def _build_confidence(self, request: EnrichmentRequest, dossier: Dossier) -> list[ConfidenceBreakdown]:
        username = request.username or (request.email or "candidate@example.com").split("@")[0]
        handle_match = any(handle.username.lower() == username.lower() for handle in dossier.handles)
        dropped = int(dossier.metadata.get("disambiguation_dropped") or 0)
        evidence = [
            f"cross-source handles: {len(dossier.handles)}",
            f"llm disambiguation dropped: {dropped}",
        ]
        if dossier.handles:
            avg = sum(handle.confidence for handle in dossier.handles) / len(dossier.handles)
            evidence.append(f"avg handle confidence: {avg:.2f}")
        return [
            ConfidenceBreakdown(
                label="identity-match",
                score=0.91 if handle_match else (0.72 if dossier.handles else 0.44),
                evidence=evidence,
            ),
            ConfidenceBreakdown(
                label="email-verification",
                score=(
                    0.89
                    if any(e.status != "disposable" for e in dossier.verified_emails)
                    else 0.22
                ),
                evidence=[
                    "verified emails: "
                    f"{sum(1 for e in dossier.verified_emails if e.status != 'disposable')}"
                ],
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
                "requested_tiers": [
                    tier.value for tier in (request.requested_tiers or list(RequestedTier))
                ],
                "identifier_summary": " • ".join([value for value in values if value]),
            }
        )
