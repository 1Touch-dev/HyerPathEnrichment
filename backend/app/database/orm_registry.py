from app.compliance.models import AuditLog, DsarRecord, SuppressionRecord
from app.database.base import Base
from app.modules.enrichment.models import JobRecord
from app.modules.signals.models import SignalRecord
from app.storage.models import PhotoCacheRecord

_ = (JobRecord, SuppressionRecord, AuditLog, DsarRecord, PhotoCacheRecord, SignalRecord)

# Re-export for alembic env after patch
__all__ = [
    "AuditLog",
    "Base",
    "DsarRecord",
    "JobRecord",
    "PhotoCacheRecord",
    "SignalRecord",
    "SuppressionRecord",
]
