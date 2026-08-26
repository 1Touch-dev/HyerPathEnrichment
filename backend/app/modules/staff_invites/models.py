"""ORM model for staff (recruiter/intern) onboarding invites. See
machine-1-tenancy-core/05-org-invite-flow.md for the accept/expiry rules that govern
this table. Unlike the superseded org-invite design, there is no seat/org membership
concept here at all -- an accepted invite just gets a role assigned on the one shared
users table, nothing more."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class StaffInvite(Base):
    """A pending invitation for an email address to join as staff (recruiter/intern/
    team_owner) with a specific role. No org/brand association -- see this chunk's
    file for why."""

    __tablename__ = "staff_invites"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # secrets.token_urlsafe(32): cryptographically random, URL-safe, ~43 chars -- not
    # a sequential id or anything derivable from email, since this token is the
    # entire bearer-credential for GET /api/staff-invites/{token} (public,
    # unauthenticated) and for redeeming staff status at signup.
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    # The role to assign on acceptance. References Role.name from the seeded
    # team_owner/recruiter rows (047_seed_system_roles) -- stored as a plain string,
    # not a FK to admin_roles.id, because this module does not import from the admin
    # module's models and because that RBAC track may not have landed yet when this
    # chunk is implemented elsewhere (graceful-degradation posture).
    role_name: Mapped[str] = mapped_column(String(64), nullable=False, default="recruiter")
    invited_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # 7 days, matching common B2B SaaS invite-expiry convention (long enough to
    # survive a slow-to-respond invitee's weekend, short enough that a stale invite
    # doesn't sit around indefinitely).
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC) + timedelta(days=7),
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
