from enum import StrEnum


class RequestedTier(StrEnum):
    tier1 = "tier1"
    tier2 = "tier2"
    tier3 = "tier3"
    tier4 = "tier4"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    suppressed = "suppressed"
    purged = "purged"


class AuditEventType(StrEnum):
    opt_out = "opt_out"
    dsar_created = "dsar_created"
    dsar_completed = "dsar_completed"
    enrichment_suppressed = "enrichment_suppressed"
    data_purged = "data_purged"
    enrichment_completed = "enrichment_completed"


class DsarType(StrEnum):
    access = "access"
    deletion = "deletion"


class DsarStatus(StrEnum):
    pending = "pending"
    completed = "completed"
    rejected = "rejected"
