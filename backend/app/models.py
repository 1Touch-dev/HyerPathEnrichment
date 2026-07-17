"""Compatibility barrel — prefer importing from domain/, modules/, compliance/, database/."""

from app.compliance.models import AuditLog, DsarRecord, SuppressionRecord
from app.database.base import Base, JsonDoc
from app.domain.dossier import (
    BusinessProfile,
    ConfidenceBreakdown,
    Dossier,
    JobListing,
    PhotoAsset,
    SocialHandle,
    VerifiedEmail,
)
from app.domain.enrichment import (
    DsarRequest,
    DsarResponse,
    EnrichmentJobListItem,
    EnrichmentJobListResponse,
    EnrichmentJobResponse,
    EnrichmentRequest,
    HealthResponse,
    SignalListItem,
    SignalListResponse,
    SuppressionCheckResponse,
    SuppressionRequest,
)
from app.domain.enums import (
    AuditEventType,
    DsarStatus,
    DsarType,
    JobStatus,
    RequestedTier,
)
from app.modules.enrichment.models import JobRecord
from app.modules.signals.models import SignalRecord
from app.storage.models import PhotoCacheRecord

__all__ = [
    "AuditEventType",
    "AuditLog",
    "Base",
    "BusinessProfile",
    "ConfidenceBreakdown",
    "Dossier",
    "DsarRecord",
    "DsarRequest",
    "DsarResponse",
    "DsarStatus",
    "DsarType",
    "EnrichmentJobListItem",
    "EnrichmentJobListResponse",
    "EnrichmentJobResponse",
    "EnrichmentRequest",
    "HealthResponse",
    "JobListing",
    "JobRecord",
    "JobStatus",
    "JsonDoc",
    "PhotoAsset",
    "PhotoCacheRecord",
    "RequestedTier",
    "SignalListItem",
    "SignalListResponse",
    "SignalRecord",
    "SocialHandle",
    "SuppressionCheckResponse",
    "SuppressionRecord",
    "SuppressionRequest",
    "VerifiedEmail",
]
