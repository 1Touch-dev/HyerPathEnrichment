from __future__ import annotations

from app.enrichers.base import Enricher
from app.enrichers.crosslinked import CrossLinkedEnricher
from app.enrichers.email_discover import EmailDiscoverEnricher
from app.enrichers.email_verify import EmailVerifyEnricher
from app.enrichers.gitrecon import GitReconEnricher
from app.enrichers.jobspy import JobSpyEnricher
from app.enrichers.linkedin_photo import LinkedInPhotoEnricher
from app.enrichers.local_business import LocalBusinessEnricher
from app.enrichers.maigret import MaigretEnricher
from app.enrichers.sherlock import SherlockEnricher
from app.enrichers.social_analyzer import SocialAnalyzerEnricher
from app.enrichers.theharvester import TheHarvesterEnricher


def tier1_enrichers() -> list[Enricher]:
    return [LinkedInPhotoEnricher()]


def tier2_enrichers() -> list[Enricher]:
    return [SherlockEnricher(), MaigretEnricher(), SocialAnalyzerEnricher()]


def tier3_discover_enrichers() -> list[Enricher]:
    return [
        GitReconEnricher(),
        TheHarvesterEnricher(),
        EmailDiscoverEnricher(),
        CrossLinkedEnricher(),
    ]


def email_verify_enricher() -> EmailVerifyEnricher:
    return EmailVerifyEnricher()


def tier4_enrichers() -> list[Enricher]:
    return [JobSpyEnricher(), LocalBusinessEnricher()]
