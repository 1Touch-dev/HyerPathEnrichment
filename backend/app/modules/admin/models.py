"""ORM models for the Admin Module: RBAC, audit log, feature flags, impersonation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, JsonDoc


class Role(Base):
    """Named collection of permissions. Distinct from `User.is_superuser`, which is
    a direct, non-grantable override — see phase2_admin_module.md Decision 1."""

    __tablename__ = "roles"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Not in phase2_admin_module.md §8.1's own models.py listing — added because
    # §8.7's repository.list_roles() calls selectinload(Role.permissions), and no
    # section of the plan actually defines this relationship (§8.8 only adds
    # User.role). viewonly=True: role/permission assignment is a straight INSERT/
    # DELETE on the role_permissions join rows (no ORM-side write path needed
    # through this collection), so this is read-only, matching how this
    # relationship is actually consumed (list_roles() only ever reads it).
    permissions: Mapped[list[Permission]] = relationship(
        "Permission", secondary="role_permissions", viewonly=True
    )


class Permission(Base):
    """One resource+action pair, e.g. ('users', 'suspend'). Not to be confused with
    `app/auth/permissions.py`, which only re-exports `VerifiedUser` — see §5."""

    __tablename__ = "permissions"
    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permissions_resource_action"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    resource: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class RolePermission(Base):
    """Join table: which permissions a role grants."""

    __tablename__ = "role_permissions"

    role_id: Mapped[UUID] = mapped_column(
        ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    )
    permission_id: Mapped[UUID] = mapped_column(
        ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True
    )


class AdminAuditLog(Base):
    """Admin-write audit trail. Deliberately separate from
    `compliance.models.AuditLog` — see §5 naming collision."""

    __tablename__ = "admin_audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # Set only when the actor was impersonating another user at the time of this
    # action (Decision 6) — the *real* admin identity, kept distinct from actor_user_id
    # which, during impersonation, is the target user (per Zendesk's warning, §5).
    impersonated_by: Mapped[UUID | None] = mapped_column(nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    # "explicit" (a router/service called record_admin_action) or "fallback"
    # (AdminAuditFallbackMiddleware caught an un-audited mutation) — see Decision 2.
    captured_by: Mapped[str] = mapped_column(String(16), default="explicit", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), index=True
    )


class FeatureFlag(Base):
    """DB-backed kill switch / config toggle. See Decision 8 — ships with no
    forced business-logic migration; infra only, until a real gate needs it."""

    __tablename__ = "feature_flags"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    value: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class ImpersonationSession(Base):
    """One support-impersonation grant. Sequenced last per §11.5 — requires the
    audit log and MFA to already exist (Decision 6)."""

    __tablename__ = "impersonation_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    admin_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AdminReviewQueueItem(Base):
    """Generic moderation review-queue row (Batch 1 — Stripe-Radar/Indeed-style
    review queue). One row per flagged resource across domains (job postings,
    documents, portfolio items, outreach messages, and later questions/
    practice_audio). Maps exactly the columns from
    alembic/versions/039_admin_review_queue.py; deliberately has no
    relationships to domain ORM models (job_matching/documents/portfolio/
    outreach) — resolution of the underlying resource is done via raw SQL in
    review_queue_router.py so this module stays decoupled from those models."""

    __tablename__ = "admin_review_queue"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    flag_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    flag_source: Mapped[str] = mapped_column(String(16), nullable=False)
    flagged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
