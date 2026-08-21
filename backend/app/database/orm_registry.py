# Module 2: Tinder-Style Job Board + CV Management — side-effect imports only,
# so Alembic autogenerate and metadata.create_all() see these ORM classes even
# when nothing else in the import graph has touched these modules yet.
import app.modules.documents.models
import app.modules.job_swipe.models
import app.modules.outreach.models
import app.modules.portfolio.models  # noqa: F401
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
from app.modules.admin.models import (
    AdminAuditLog,
    FeatureFlag,
    ImpersonationSession,
    Permission,
    Role,
    RolePermission,
)
from app.modules.enrichment.models import JobRecord
from app.modules.job_matching.models import (
    CandidateJobPreferences,
    JobMatch,
    JobPosting,
    JobPostingEmbedding,
    PushSubscription,
)
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
    CandidateJobPreferences,
    JobMatch,
    JobPosting,
    JobPostingEmbedding,
    PushSubscription,
    Role,
    Permission,
    RolePermission,
    AdminAuditLog,
    FeatureFlag,
    ImpersonationSession,
)

# Re-export for alembic env after patch
__all__ = [
    "AdminAuditLog",
    "AuditLog",
    "AuthAuditLog",
    "Base",
    "CandidateJobPreferences",
    "DsarRecord",
    "EmailVerificationToken",
    "FeatureFlag",
    "ImpersonationSession",
    "JobMatch",
    "JobPosting",
    "JobPostingEmbedding",
    "JobRecord",
    "LoggedOutToken",
    "OAuthAccount",
    "Permission",
    "PhotoCacheRecord",
    "PracticeSession",
    "PushSubscription",
    "QuestionAttempt",
    "RefreshToken",
    "Role",
    "RolePermission",
    "SignalRecord",
    "SuppressionRecord",
    "TokenBlacklist",
    "User",
]
