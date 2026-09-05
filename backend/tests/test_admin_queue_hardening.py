"""Focused security contract tests for ADMIN-BE-005 queue administration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import func, select

from app.auth.dependencies import get_current_user_from_cookie, require_verified_user
from app.auth.jwt_tokens import create_user_access_token
from app.core.config import get_settings
from app.modules.admin.audit import _build_fallback_action
from app.modules.admin.models import AdminAuditLog, PrivilegedIdempotencyRecord, Role
from app.modules.admin.queues_service import REDACTED_FAILURE_DETAIL
from app.workers.queue import QUEUE_PRIORITIES
from tests.envelope_helpers import assert_error


def _queue_name() -> str:
    return next(iter(QUEUE_PRIORITIES))


async def _make_team_owner(db_session, regular_user):
    role = (await db_session.execute(select(Role).where(Role.name == "team_owner"))).scalar_one()
    regular_user.role_id = role.id
    await db_session.commit()
    await db_session.refresh(regular_user)
    return regular_user


async def test_queue_inspection_denies_roleless_candidate(client, regular_user, auth_headers):
    response = client.get("/api/admin/queues", headers=auth_headers(regular_user.id))
    assert_error(response, 403)


async def test_authorized_failed_job_inspection_is_redacted(
    client, regular_user, auth_headers, db_session
):
    owner = await _make_team_owner(db_session, regular_user)
    secret = "candidate@example.com token=super-secret"
    job = MagicMock()
    job.id = "job-1"
    job.func_name = "app.workers.tasks.email.send_email_task"
    job.enqueued_at = None
    job.ended_at = None
    job.exc_info = f"ValueError: {secret}"
    queue = MagicMock()
    queue.fetch_job.return_value = job
    registry = MagicMock()
    registry.get_job_ids.return_value = ["job-1"]

    with (
        patch("app.modules.admin.queues_service.get_redis_connection"),
        patch("app.modules.admin.queues_service.Queue", return_value=queue),
        patch("app.modules.admin.queues_service.FailedJobRegistry", return_value=registry),
    ):
        response = client.get(
            f"/api/admin/queues/{_queue_name()}/failed",
            headers=auth_headers(owner.id),
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload[0]["exc_info"] == REDACTED_FAILURE_DETAIL
    assert secret not in response.text


def test_retry_openapi_documents_no_success_response(client):
    operation = client.get("/openapi.json").json()["paths"][
        "/api/admin/queues/{name}/failed/{job_id}/retry"
    ]["post"]
    assert "405" in operation["responses"]
    assert operation["responses"]["405"]["description"].startswith(
        "Queue administration is read-only"
    )
    assert not any(code.startswith("2") for code in operation["responses"])


@pytest.mark.parametrize(
    "queue_name",
    [*QUEUE_PRIORITIES, "unregistered-queue", "__malformed_queue__"],
)
@pytest.mark.parametrize(
    "job_id",
    [
        "ordinary-job",
        "not-a-valid-rq-job-id",
        "email-delivery-job",
        "cleanup-purge-job",
        "destructive-delete-job",
    ],
)
async def test_every_queue_and_job_type_is_denied_before_redis_mutation(
    client, superuser, auth_headers, queue_name, job_id
):
    with patch("app.modules.admin.queues_service.get_redis_connection") as connection:
        response = client.post(
            f"/api/admin/queues/{queue_name}/failed/{job_id}/retry",
            headers=auth_headers(superuser.id),
        )

    assert_error(response, 405, "QUEUE_ADMIN_READ_ONLY")
    connection.assert_not_called()


async def test_authorized_retry_returns_stable_read_only_error_and_writes_no_success_state(
    client, regular_user, auth_headers, db_session
):
    owner = await _make_team_owner(db_session, regular_user)
    path = f"/api/admin/queues/{_queue_name()}/failed/email-delivery-job/retry"
    fallback_action = _build_fallback_action("POST", path)
    request_id = "queue-retry-authorized-read-only"

    success_audits_before = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(AdminAuditLog.action == "queues.retry_failed_job")
    )
    idempotency_before = await db_session.scalar(
        select(func.count()).select_from(PrivilegedIdempotencyRecord)
    )
    fallback_before = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(AdminAuditLog.action == fallback_action)
    )

    with patch("app.modules.admin.queues_service.get_redis_connection") as connection:
        response = client.post(
            path,
            headers={
                **auth_headers(owner.id),
                "X-Request-ID": request_id,
            },
        )

    assert_error(response, 405, "QUEUE_ADMIN_READ_ONLY")
    connection.assert_not_called()

    success_audits_after = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(AdminAuditLog.action == "queues.retry_failed_job")
    )
    idempotency_after = await db_session.scalar(
        select(func.count()).select_from(PrivilegedIdempotencyRecord)
    )
    fallback_after = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(AdminAuditLog.action == fallback_action)
    )
    assert success_audits_after == success_audits_before
    assert idempotency_after == idempotency_before
    assert fallback_after == fallback_before + 1

    fallback = (
        await db_session.execute(
            select(AdminAuditLog).where(AdminAuditLog.request_id == request_id)
        )
    ).scalar_one()
    assert fallback.action == fallback_action
    assert fallback.captured_by == "fallback"
    assert fallback.actor_user_id == owner.id
    assert fallback.outcome == "denied"
    assert fallback.after == {"status_code": 405}


async def test_unauthorized_retry_is_denied_without_redis(client, regular_user, db_session):
    from app.main import app

    path = f"/api/admin/queues/{_queue_name()}/failed/job-1/retry"
    fallback_action = _build_fallback_action("POST", path)
    request_id = "queue-retry-unauthorized-denial"
    settings = get_settings()
    access_token, _ = create_user_access_token(
        str(regular_user.id),
        regular_user.email,
        secret_key=settings.SECRET_KEY,
        expires_minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    )
    success_audits_before = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(AdminAuditLog.action == "queues.retry_failed_job")
    )
    idempotency_before = await db_session.scalar(
        select(func.count()).select_from(PrivilegedIdempotencyRecord)
    )
    fallback_before = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(AdminAuditLog.action == fallback_action)
    )
    overridden_dependencies = {
        dependency: app.dependency_overrides.pop(dependency)
        for dependency in (get_current_user_from_cookie, require_verified_user)
        if dependency in app.dependency_overrides
    }
    try:
        with patch("app.modules.admin.queues_service.get_redis_connection") as connection:
            response = client.post(
                path,
                headers={
                    "Cookie": f"access_token={access_token}",
                    "X-Request-ID": request_id,
                },
            )
    finally:
        app.dependency_overrides.update(overridden_dependencies)
    assert_error(response, 403)
    connection.assert_not_called()
    success_audits_after = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(AdminAuditLog.action == "queues.retry_failed_job")
    )
    idempotency_after = await db_session.scalar(
        select(func.count()).select_from(PrivilegedIdempotencyRecord)
    )
    fallback_after = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(AdminAuditLog.action == fallback_action)
    )
    assert success_audits_after == success_audits_before
    assert idempotency_after == idempotency_before
    assert fallback_after == fallback_before + 1
    fallback = (
        await db_session.execute(
            select(AdminAuditLog).where(AdminAuditLog.request_id == request_id)
        )
    ).scalar_one()
    assert fallback.action == fallback_action
    assert fallback.captured_by == "fallback"
    assert fallback.actor_user_id == regular_user.id
    assert fallback.outcome == "denied"
    assert fallback.after == {"status_code": 403}


async def test_unauthenticated_retry_receives_authentication_denial(client):
    with patch("app.modules.admin.queues_service.get_redis_connection") as connection:
        response = client.post(f"/api/admin/queues/{_queue_name()}/failed/job-1/retry")
    assert_error(response, 401)
    connection.assert_not_called()
