"""Pydantic schemas for the Admin Module API."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    is_system: bool


class PermissionResponse(BaseModel):
    id: UUID
    resource: str
    action: str
    description: str | None


class RoleWithPermissionsResponse(RoleResponse):
    permissions: list[PermissionResponse]


class CreateRoleRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=1000)


class AttachPermissionRequest(BaseModel):
    permission_id: UUID


class AdminUserResponse(BaseModel):
    id: UUID
    email: str
    first_name: str
    last_name: str
    is_active: bool
    is_verified: bool
    is_superuser: bool
    role_id: UUID | None
    role_name: str | None
    mfa_enabled: bool
    created_at: datetime
    deleted_at: datetime | None


class AdminUserListResponse(BaseModel):
    items: list[AdminUserResponse]
    next_cursor: str | None
    has_more: bool


class UpdateUserStatusRequest(BaseModel):
    is_active: bool
    reason: str | None = Field(default=None, max_length=500)


class AssignRoleRequest(BaseModel):
    role_id: UUID | None  # None clears the role


class AdminAuditLogEntryResponse(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    impersonated_by: UUID | None
    impersonation_session_id: UUID | None
    request_id: str | None
    outcome: str | None
    action: str
    target_type: str
    target_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip_address: str | None
    captured_by: str
    created_at: datetime


class AdminAuditLogListResponse(BaseModel):
    items: list[AdminAuditLogEntryResponse]
    next_cursor: str | None
    has_more: bool


class FeatureFlagResponse(BaseModel):
    key: str
    enabled: bool
    value: dict[str, Any] | None
    description: str | None
    updated_by: UUID | None
    updated_at: datetime


class UpsertFeatureFlagRequest(BaseModel):
    enabled: bool
    value: dict[str, Any] | None = None
    description: str | None = None


class QueueSnapshotResponse(BaseModel):
    name: str
    priority: int
    queued_count: int
    failed_count: int
    oldest_queued_age_seconds: float | None
    workers_listening: int


class QueuesOverviewResponse(BaseModel):
    queues: list[QueueSnapshotResponse]


class FailedJobResponse(BaseModel):
    job_id: str
    queue_name: str
    func_name: str | None
    enqueued_at: datetime | None
    failed_at: datetime | None
    exc_info: str | None


class SystemHealthResponse(BaseModel):
    database_ok: bool
    database_latency_ms: float
    redis_ok: bool
    redis_latency_ms: float
    prometheus_configured: bool
    # Four golden signals — populated only when PROMETHEUS_QUERY_URL is set (§7);
    # empty dict is the fail-soft shape, matching this repo's other optional-backend
    # conventions rather than raising.
    signals: dict[str, float | None]


class JobMatchAnalyticsResponse(BaseModel):
    """Ground-truth-correction analytics (§3) — aggregate over job_postings/job_matches.
    Explicitly NOT a BI dashboard, per docs/admin-module-research.md §6's own
    'handful of aggregate queries' scope boundary."""

    total_postings: int
    total_matches: int
    postings_by_source: dict[str, int]
    top_companies: list[dict[str, Any]]
    avg_salary_min: float | None
    avg_salary_max: float | None
    avg_overall_score: float | None
    computed_at: datetime
    cache_hit: bool


class MfaEnrollResponse(BaseModel):
    secret: str
    provisioning_uri: str


class MfaVerifyRequest(BaseModel):
    code: str = Field(min_length=6, max_length=6)


class MfaEnrollRequest(BaseModel):
    current_code: str | None = Field(default=None, min_length=6, max_length=6)


class MfaStatusResponse(BaseModel):
    mfa_enabled: bool
    mfa_enrolled_at: datetime | None


class ImpersonationStartRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=6)


class ImpersonationStartResponse(BaseModel):
    target_user_id: UUID
    expires_at: datetime


class ImpersonationStatusResponse(BaseModel):
    is_impersonating: bool
    admin_user_id: UUID | None
    admin_email: str | None
    target_user_id: UUID | None
    expires_at: datetime | None
