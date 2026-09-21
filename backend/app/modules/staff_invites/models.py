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
    """A recruiter-only staff invitation with no org/brand association."""

    __tablename__ = "staff_invites"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # Transitional plaintext column. Current writes leave it NULL; revision
    # 065 retains safe active values only for hardened restored-schema
    # recovery, never to support a pre-hardening binary.
    token: Mapped[str | None] = mapped_column(String(64), unique=True, nullable=True, index=True)
    # Authoritative bearer-credential digest. Nullable only for the bounded
    # restored-schema fallback described in repository.get_invite_by_token().
    token_digest: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    # Legacy display value retained during transition; redemption additionally
    # requires role_id to reference the seeded recruiter role.
    role_name: Mapped[str] = mapped_column(String(64), nullable=False, default="recruiter")
    role_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"), nullable=True
    )
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
    accepted_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
