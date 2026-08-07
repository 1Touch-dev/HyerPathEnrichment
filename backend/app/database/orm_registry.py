from app.auth.models import (
    AuthAuditLog,
    EmailVerificationToken,
    LoggedOutToken,
    OAuthAccount,
    RefreshToken,
    TokenBlacklist,
    User,
)
from app.compliance.models import AuditLog, DsarRecord, SuppressionRecord
from app.database.base import Base
from app.modules.enrichment.models import JobRecord
from app.modules.sessions.models import PracticeSession, QuestionAttempt
from app.modules.signals.models import SignalRecord
from app.storage.models import PhotoCacheRecord

_ = (
    JobRecord,
    SuppressionRecord,
    AuditLog,
    DsarRecord,
    PhotoCacheRecord,
    SignalRecord,
    User,
    OAuthAccount,
    RefreshToken,
    TokenBlacklist,
    EmailVerificationToken,
    LoggedOutToken,
    AuthAuditLog,
    PracticeSession,
    QuestionAttempt,
)

# Re-export for alembic env after patch
__all__ = [
    "AuditLog",
    "AuthAuditLog",
    "Base",
    "DsarRecord",
    "EmailVerificationToken",
    "JobRecord",
    "LoggedOutToken",
    "OAuthAccount",
    "PhotoCacheRecord",
    "PracticeSession",
    "QuestionAttempt",
    "RefreshToken",
    "SignalRecord",
    "SuppressionRecord",
    "TokenBlacklist",
    "User",
]
