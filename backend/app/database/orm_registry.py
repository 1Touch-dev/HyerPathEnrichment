from app.modules.enrichment import models as enrichment_models  # noqa: F401
from app.compliance import models as compliance_models  # noqa: F401
from app.modules.signals import models as signals_models  # noqa: F401
from app.storage import models as storage_models  # noqa: F401
from app.database.base import Base
from app.compliance.models import AuditLog, DsarRecord, SuppressionRecord
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
