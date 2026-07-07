from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from uuid import uuid4

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
from app.llm_router import LiteLLMDisambiguator
from app.models import Dossier, EnrichmentRequest, JobRecord, JobStatus, SuppressionRecord


class PipelineOrchestrator:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.llm = LiteLLMDisambiguator()
        self.tier1 = [LinkedInPhotoEnricher()]
        self.tier2 = [SherlockEnricher(), MaigretEnricher(), SocialAnalyzerEnricher()]
        self.tier3 = [GitReconEnricher(), TheHarvesterEnricher(), EmailDiscoverEnricher(), EmailVerifyEnricher(), CrossLinkedEnricher()]
        self.tier4 = [JobSpyEnricher(), LocalBusinessEnricher()]

    async def run(self, request: EnrichmentRequest) -> JobRecord:
        suppressed = await self._is_suppressed(request)
        job = JobRecord(
            id=f"job_{uuid4().hex}",
            status=JobStatus.suppressed.value if suppressed else JobStatus.running.value,
            request_payload=request.model_dump(mode="json"),
            dossier_payload={},
        )
        self.db.add(job)
        await self.db.flush()

        if suppressed:
            dossier = self._base_dossier(request)
            dossier.metadata["suppressed"] = True
            job.status = JobStatus.suppressed.value
            job.dossier_payload = dossier.model_dump(mode="json")
            await self.db.commit()
            await self.db.refresh(job)
            return job

        payloads = await self._dispatch(request)
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
        record = SuppressionRecord(identifier_hash=self._hash(identifier), reason=reason or "")
        self.db.merge(record)
        await self.db.commit()

    async def check_suppression(self, identifier: str) -> bool:
        statement = select(SuppressionRecord).where(SuppressionRecord.identifier_hash == self._hash(identifier))
        result = await self.db.execute(statement)
        return result.scalar_one_or_none() is not None

    async def _is_suppressed(self, request: EnrichmentRequest) -> bool:
        identifiers = [request.email, request.linkedin_url, request.username, request.company, request.business, request.job_search]
        for identifier in [value for value in identifiers if value]:
            if await self.check_suppression(identifier):
                return True
        return False

    async def _dispatch(self, request: EnrichmentRequest) -> list[dict[str, object]]:
        enrichers = []
        if "tier1" in request.requested_tiers:
            enrichers.extend(self.tier1)
        if "tier2" in request.requested_tiers:
            enrichers.extend(self.tier2)
        if "tier3" in request.requested_tiers:
            enrichers.extend(self.tier3)
        if "tier4" in request.requested_tiers:
            enrichers.extend(self.tier4)

        async def invoke(enricher: object) -> dict[str, object]:
            worker = enricher
            if not await worker.validate(request):
                return {}
            await worker.initialize()
            try:
                payload = await worker.run(request)
                payload = await worker.normalize(payload)
                return await worker.score(payload)
            finally:
                await worker.cleanup()

        return await asyncio.gather(*(invoke(enricher) for enricher in enrichers))

    async def _merge(self, request: EnrichmentRequest, payloads: list[dict[str, object]]) -> Dossier:
        dossier = self._base_dossier(request)
        handles_seen: set[tuple[str, str]] = set()
        emails_seen: set[str] = set()
        sources: set[str] = set()

        for payload in payloads:
            photo = payload.get("photo")
            if photo and dossier.photo is None:
                dossier.photo = photo  # type: ignore[assignment]

            for handle in payload.get("handles", []):
                key = (str(handle["platform"]).lower(), str(handle["username"]).lower())
                if key not in handles_seen:
                    handles_seen.add(key)
                    dossier.handles.append(handle)  # type: ignore[arg-type]

            for email in payload.get("emails", []):
                normalized = str(email).lower()
                if normalized not in emails_seen:
                    emails_seen.add(normalized)
                    dossier.emails.append(str(email))

            for verified in payload.get("verified_emails", []):
                if verified["value"].lower() not in {item.value.lower() for item in dossier.verified_emails}:
                    dossier.verified_emails.append(verified)  # type: ignore[arg-type]

            if payload.get("github"):
                dossier.github = payload["github"]  # type: ignore[assignment]

            for coworker in payload.get("coworkers", []):
                if coworker not in dossier.coworkers:
                    dossier.coworkers.append(str(coworker))

            for job in payload.get("jobs", []):
                if job not in [existing.model_dump(mode="json") for existing in dossier.jobs]:
                    dossier.jobs.append(job)  # type: ignore[arg-type]

            if payload.get("business") and dossier.business is None:
                dossier.business = payload["business"]  # type: ignore[assignment]

            for source in payload.get("sources", []):
                sources.add(str(source))

        dossier.sources = sorted(sources)
        dossier.confidence = await self._build_confidence(request, dossier)
        return dossier

    async def _build_confidence(self, request: EnrichmentRequest, dossier: Dossier) -> list[dict[str, object]]:
        username = request.username or (request.email or "candidate@example.com").split("@")[0]
        handle_match = any(handle.username.lower() == username.lower() for handle in dossier.handles)
        decision = await self.llm.compare(username, username if handle_match else "unknown")
        return [
            {
                "label": "identity-match",
                "score": 0.91 if handle_match else 0.44,
                "evidence": [
                    f"cross-source handles: {len(dossier.handles)}",
                    f"llm confirmation: {decision.same_identity} ({decision.reason})",
                ],
            },
            {
                "label": "email-verification",
                "score": 0.89 if dossier.verified_emails else 0.22,
                "evidence": [f"verified emails: {len(dossier.verified_emails)}"],
            },
            {
                "label": "coverage",
                "score": min(1.0, 0.2 + (len(dossier.sources) * 0.1)),
                "evidence": [f"sources: {', '.join(dossier.sources) or 'none'}"],
            },
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
