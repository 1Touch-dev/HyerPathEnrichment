"""Deterministic dossier assembly — no LLM calls."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.domain.dossier import (
    BusinessProfile,
    ConfidenceBreakdown,
    Dossier,
    JobListing,
    PhotoAsset,
    SocialHandle,
    VerifiedEmail,
)
from app.domain.enrichment import EnrichmentRequest
from app.domain.enums import RequestedTier

_COMPANY_SUFFIXES = re.compile(
    r"\b(inc\.?|llc\.?|l\.?l\.?c\.?|corp\.?|corporation|ltd\.?|limited|co\.?)\s*$",
    re.IGNORECASE,
)


def base_dossier(request: EnrichmentRequest) -> Dossier:
    values = [
        request.email,
        request.linkedin_url,
        request.username,
        request.company,
        request.business,
        request.job_search,
    ]
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


def normalize_job_key(title: str, company: str, location: str) -> str:
    def norm(text: str) -> str:
        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        return re.sub(r"\s+", " ", cleaned).strip()

    company_norm = _COMPANY_SUFFIXES.sub("", norm(company)).strip()
    return f"{norm(title)}|{company_norm}|{norm(location)}"


def job_location_specificity(location: str) -> int:
    loc = location.strip().lower()
    if not loc or loc in {"remote", "anywhere"}:
        return 0
    return len(loc.split(",")) + len(loc.split())


def merge_payloads(request: EnrichmentRequest, payloads: list[dict[str, Any]]) -> Dossier:
    """Fold enricher fragments into a dossier (before disambiguation)."""
    dossier = base_dossier(request)
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
                verified_candidate = VerifiedEmail.model_validate(verified)
                if verified_candidate.value.lower() not in {
                    item.value.lower() for item in dossier.verified_emails
                }:
                    dossier.verified_emails.append(verified_candidate)

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
                job_key = normalize_job_key(
                    job_candidate.title,
                    job_candidate.company,
                    job_candidate.location,
                )
                if job_key not in jobs_seen:
                    jobs_seen[job_key] = len(dossier.jobs)
                    dossier.jobs.append(job_candidate)
                    continue
                existing_idx = jobs_seen[job_key]
                existing = dossier.jobs[existing_idx]
                if job_location_specificity(job_candidate.location) > job_location_specificity(
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
    return dossier


def build_confidence(request: EnrichmentRequest, dossier: Dossier) -> list[ConfidenceBreakdown]:
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
