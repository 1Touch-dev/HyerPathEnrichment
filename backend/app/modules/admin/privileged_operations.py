"""Central ADR 0021 privileged-operation catalog and enforcement helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, ForbiddenError, ValidationAppError
from app.core.logging import get_request_id
from app.modules.admin import privileged_operations_repository
from app.modules.admin.models import PrivilegedIdempotencyRecord

PrivilegedOperationLevel = str


@dataclass(frozen=True)
class PrivilegedOperationSpec:
    operation_id: str
    level: PrivilegedOperationLevel
    unavailable_reason: str | None = None
    unavailable_code: str | None = None


@dataclass(frozen=True)
class IdempotentReplay:
    status_code: int
    response_body: dict[str, Any]


@dataclass(frozen=True)
class PrivilegedRequestState:
    operation_id: str
    request_id: str
    record: PrivilegedIdempotencyRecord


PRIVILEGED_OPERATION_CATALOG: dict[str, PrivilegedOperationSpec] = {
    "staff_invite.issued": PrivilegedOperationSpec("staff_invite.issued", "P3"),
    "user.status.deactivate": PrivilegedOperationSpec(
        "user.status.deactivate",
        "UNAVAILABLE",
        "User deactivation is unavailable until typed confirmation and step-up are implemented.",
    ),
    "user.status.reactivate": PrivilegedOperationSpec("user.status.reactivate", "P1"),
    "user.role.assign": PrivilegedOperationSpec(
        "user.role.assign",
        "UNAVAILABLE",
        "Role assignment is unavailable until typed confirmation and step-up are implemented.",
    ),
    "role.create": PrivilegedOperationSpec(
        "role.create",
        "UNAVAILABLE",
        "Role creation is unavailable until typed confirmation and step-up are implemented.",
    ),
    "role.attach_permission": PrivilegedOperationSpec(
        "role.attach_permission",
        "UNAVAILABLE",
        "Role permission changes are unavailable until typed confirmation and step-up are implemented.",
    ),
    "role.detach_permission": PrivilegedOperationSpec(
        "role.detach_permission",
        "UNAVAILABLE",
        "Role permission changes are unavailable until typed confirmation and step-up are implemented.",
    ),
    "impersonation.started": PrivilegedOperationSpec("impersonation.started", "P2"),
    "impersonation.ended": PrivilegedOperationSpec("impersonation.ended", "P2"),
    "mfa.enrollment_started": PrivilegedOperationSpec("mfa.enrollment_started", "P2"),
    "mfa.enrollment_confirmed": PrivilegedOperationSpec("mfa.enrollment_confirmed", "P2"),
    "mfa.disabled": PrivilegedOperationSpec("mfa.disabled", "P2"),
    "brand.create": PrivilegedOperationSpec("brand.create", "P1"),
    "brand.update": PrivilegedOperationSpec("brand.update", "P1"),
    "brand.deactivate": PrivilegedOperationSpec("brand.deactivate", "P1"),
    "brand.reactivate": PrivilegedOperationSpec("brand.reactivate", "P1"),
    "documents.moderate": PrivilegedOperationSpec("documents.moderate", "P1"),
    "job_postings.moderate": PrivilegedOperationSpec("job_postings.moderate", "P1"),
    "questions.moderate": PrivilegedOperationSpec("questions.moderate", "P1"),
    "practice_audio.moderate": PrivilegedOperationSpec("practice_audio.moderate", "P1"),
    "outreach.moderate": PrivilegedOperationSpec("outreach.moderate", "P1"),
    "portfolio.moderate": PrivilegedOperationSpec("portfolio.moderate", "P1"),
    "interview_schedules.moderate": PrivilegedOperationSpec("interview_schedules.moderate", "P1"),
    "manual_job_entries.moderate": PrivilegedOperationSpec("manual_job_entries.moderate", "P1"),
    "review_queue.decide": PrivilegedOperationSpec("review_queue.decide", "P1"),
    "feature_flags.mutate": PrivilegedOperationSpec(
        "feature_flags.mutate",
        "UNAVAILABLE",
        "Feature flag mutation is disabled until an application consumer exists.",
        "FEATURE_FLAGS_READ_ONLY",
    ),
    "queues.retry_failed_job": PrivilegedOperationSpec(
        "queues.retry_failed_job",
        "UNAVAILABLE",
        "Queue administration is read-only; retry is unavailable until replay-safe controls exist.",
        "QUEUE_ADMIN_READ_ONLY",
    ),
}


EXPECTED_PRIVILEGED_ROUTE_OPERATIONS: dict[tuple[str, str], tuple[str, ...]] = {
    ("POST", "/api/staff-invites"): ("staff_invite.issued",),
    ("PATCH", "/api/admin/users/{user_id}/status"): (
        "user.status.deactivate",
        "user.status.reactivate",
    ),
    ("PUT", "/api/admin/users/{user_id}/role"): ("user.role.assign",),
    ("POST", "/api/admin/roles"): ("role.create",),
    ("POST", "/api/admin/roles/{role_id}/permissions"): ("role.attach_permission",),
    ("DELETE", "/api/admin/roles/{role_id}/permissions/{permission_id}"): (
        "role.detach_permission",
    ),
    ("POST", "/api/admin/impersonation/start/{user_id}"): ("impersonation.started",),
    ("POST", "/api/admin/impersonation/end"): ("impersonation.ended",),
    ("POST", "/api/admin/mfa/enroll"): ("mfa.enrollment_started",),
    ("POST", "/api/admin/mfa/confirm"): ("mfa.enrollment_confirmed",),
    ("POST", "/api/admin/mfa/disable"): ("mfa.disabled",),
    ("POST", "/api/admin/brands"): ("brand.create",),
    ("PATCH", "/api/admin/brands/{brand_id}"): ("brand.update",),
    ("POST", "/api/admin/brands/{brand_id}/deactivate"): ("brand.deactivate",),
    ("POST", "/api/admin/brands/{brand_id}/reactivate"): ("brand.reactivate",),
    ("POST", "/api/admin/documents/{document_id}/moderate"): ("documents.moderate",),
    ("POST", "/api/admin/job-postings/{job_posting_id}/moderate"): ("job_postings.moderate",),
    ("POST", "/api/admin/questions/{question_id}/moderate"): ("questions.moderate",),
    ("POST", "/api/admin/practice-audio/{recording_id}/moderate"): ("practice_audio.moderate",),
    ("POST", "/api/admin/outreach/{message_id}/moderate"): ("outreach.moderate",),
    ("POST", "/api/admin/portfolio/{profile_id}/moderate"): ("portfolio.moderate",),
    ("POST", "/api/admin/interview-schedules/{schedule_id}/moderate"): (
        "interview_schedules.moderate",
    ),
    ("POST", "/api/admin/manual-job-entries/{entry_id}/moderate"): ("manual_job_entries.moderate",),
    ("POST", "/api/admin/review-queue/{item_id}/decide"): ("review_queue.decide",),
    ("PUT", "/api/admin/feature-flags/{key}"): ("feature_flags.mutate",),
    ("POST", "/api/admin/feature-flags"): ("feature_flags.mutate",),
    ("PATCH", "/api/admin/feature-flags/{key}"): ("feature_flags.mutate",),
    ("DELETE", "/api/admin/feature-flags/{key}"): ("feature_flags.mutate",),
    ("POST", "/api/admin/queues/{name}/failed/{job_id}/retry"): ("queues.retry_failed_job",),
}


def operation_for_user_status(*, is_active: bool) -> str:
    return "user.status.reactivate" if is_active else "user.status.deactivate"


def get_operation_spec(operation_id: str) -> PrivilegedOperationSpec:
    spec = PRIVILEGED_OPERATION_CATALOG.get(operation_id)
    if spec is None:
        raise AppError(
            "PRIVILEGED_OPERATION_UNCLASSIFIED",
            "This privileged operation is not classified and remains unavailable.",
            405,
        )
    return spec


def assert_operation_available(operation_id: str) -> PrivilegedOperationSpec:
    spec = get_operation_spec(operation_id)
    if spec.level == "UNAVAILABLE":
        raise AppError(
            spec.unavailable_code or "PRIVILEGED_OPERATION_UNAVAILABLE",
            spec.unavailable_reason or "This privileged operation is unavailable.",
            405,
        )
    return spec


def require_idempotency_key(operation_id: str, idempotency_key: str | None) -> str:
    spec = assert_operation_available(operation_id)
    if spec.level not in {"P1", "P2", "P3"}:
        return ""
    normalized = (idempotency_key or "").strip()
    if not normalized:
        raise ValidationAppError("Idempotency-Key must not be blank")
    return normalized


def require_recent_step_up(*, verified: bool) -> None:
    if not verified:
        raise ForbiddenError("Recent step-up authentication required")


def require_typed_confirmation(*, expected: str, actual: str, label: str) -> None:
    if actual.casefold() != expected.casefold():
        raise ValidationAppError(f"Typed confirmation must match the {label}")


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    def normalize(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(key): normalize(inner) for key, inner in sorted(value.items())}
        if isinstance(value, (list, tuple)):
            return [normalize(item) for item in value]
        return value

    canonical = json.dumps(normalize(payload), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _aware(dt: datetime) -> datetime:
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt


def _replay_response(
    record: PrivilegedIdempotencyRecord,
    *,
    request_hash: str,
) -> IdempotentReplay:
    if record.request_hash != request_hash:
        raise AppError(
            "IDEMPOTENCY_KEY_REUSED",
            "Idempotency key was already used for a different request",
            409,
        )
    if record.completed_at is None:
        raise AppError(
            "IDEMPOTENCY_REQUEST_IN_PROGRESS",
            "An equivalent request is already in progress",
            409,
        )
    if _aware(record.expires_at) <= datetime.now(UTC):
        raise AppError(
            "IDEMPOTENCY_REPLAY_EXPIRED",
            "The idempotent response replay window has expired",
            409,
        )
    if record.response_status is None or record.response_body is None:
        raise AppError(
            "IDEMPOTENCY_REPLAY_UNAVAILABLE",
            "The idempotent response cannot be replayed",
            409,
        )
    return IdempotentReplay(
        status_code=record.response_status,
        response_body=record.response_body,
    )


async def begin_idempotent_operation(
    db: AsyncSession,
    *,
    caller_user_id: UUID,
    operation_id: str,
    idempotency_key: str,
    request_hash: str,
) -> tuple[PrivilegedRequestState | None, IdempotentReplay | None]:
    request_id = get_request_id()
    if not request_id:
        request_id = uuid4().hex

    existing_record = await privileged_operations_repository.get_idempotency_record(
        db,
        caller_user_id=caller_user_id,
        operation=operation_id,
        idempotency_key=idempotency_key,
    )
    if existing_record is not None:
        return None, _replay_response(existing_record, request_hash=request_hash)

    try:
        record = await privileged_operations_repository.create_idempotency_record(
            db,
            caller_user_id=caller_user_id,
            operation=operation_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash,
            request_id=request_id,
        )
    except IntegrityError:
        await db.rollback()
        concurrent_record = await privileged_operations_repository.get_idempotency_record(
            db,
            caller_user_id=caller_user_id,
            operation=operation_id,
            idempotency_key=idempotency_key,
        )
        if concurrent_record is None:
            raise
        return None, _replay_response(concurrent_record, request_hash=request_hash)

    return PrivilegedRequestState(
        operation_id=operation_id, request_id=request_id, record=record
    ), None


async def complete_idempotent_operation(
    db: AsyncSession,
    state: PrivilegedRequestState,
    *,
    response_status: int,
    response_body: dict[str, Any],
) -> None:
    await privileged_operations_repository.complete_idempotency_record(
        db,
        state.record,
        response_status=response_status,
        response_body=response_body,
    )
