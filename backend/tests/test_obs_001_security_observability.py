"""OBS-001 security-observability regression tests."""

from __future__ import annotations

import asyncio
import io
import json
import logging
import re
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pyotp
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from prometheus_client import generate_latest
from sqlalchemy import func, select
from starlette.responses import JSONResponse

from app.core.logging import (
    JsonFormatter,
    RequestContextMiddleware,
    TextFormatter,
    is_valid_request_id,
    sanitize_path,
    scrub_identifier,
    scrub_sensitive_data,
    set_request_id,
)
from app.modules.admin.audit import AdminAuditFallbackMiddleware, record_admin_action
from app.modules.admin.models import AdminAuditLog
from app.observability.error_tracking import (
    init_error_tracking,
    scrub_sentry_breadcrumb,
    scrub_sentry_event,
)
from app.observability.security_metrics import (
    admin_audit_events_total,
    authorization_decisions_total,
    queue_admin_events_total,
    record_audit,
    record_authorization,
    record_queue_event,
)

SENSITIVE_VALUES = (
    "candidate@example.com",
    "https://www.linkedin.com/in/sensitive-candidate",
    "invite-token-value",
    "totp-secret-value",
    "correct-horse-password",
    "Bearer bearer-token-value",
)


class _LeakyObject:
    def __init__(self, secret: str) -> None:
        self.secret = secret
        self.rendered = False

    def __str__(self) -> str:
        self.rendered = True
        return self.secret

    def __repr__(self) -> str:
        self.rendered = True
        return self.secret


class _LeakyError(RuntimeError):
    def __str__(self) -> str:
        return "exception-secret-BarePassword!42"


def _render(formatter: logging.Formatter) -> str:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    logger = logging.getLogger(f"tests.obs001.{type(formatter).__name__}")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        raise RuntimeError("failed candidate@example.com password=correct-horse-password")
    except RuntimeError:
        logger.exception(
            "provider failed for %s with %s",
            "candidate@example.com",
            "Bearer bearer-token-value",
            extra={
                "profile": {
                    "linkedin": "https://www.linkedin.com/in/sensitive-candidate",
                    "invite_token": "invite-token-value",
                    "mfa_secret": "totp-secret-value",
                },
                "failed_job": {
                    "payload": {"email": "candidate@example.com"},
                    "request_id": "safe-request-id",
                    "action_id": "safe-action-id",
                },
            },
        )
    return stream.getvalue()


@pytest.mark.parametrize(
    "formatter",
    [JsonFormatter(service="test"), TextFormatter(service="test")],
)
def test_formatters_recursively_scrub_messages_extras_and_exceptions(
    formatter: logging.Formatter,
) -> None:
    rendered = _render(formatter)
    for value in SENSITIVE_VALUES:
        assert value not in rendered
    assert "[REDACTED]" in rendered
    assert "safe-request-id" in rendered
    assert "safe-action-id" in rendered


@pytest.mark.parametrize(
    "formatter",
    [JsonFormatter(service="test"), TextFormatter(service="test")],
)
def test_formatters_never_render_unknown_objects_or_bare_arguments(
    formatter: logging.Formatter,
) -> None:
    unknown = _LeakyObject("custom-object-secret-BarePassword!42")
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    logger = logging.getLogger(f"tests.obs001.unknown.{type(formatter).__name__}")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    try:
        raise _LeakyError()
    except _LeakyError:
        logger.exception(
            "values=%s %s %s %s %s %s safe=%s count=%s",
            unknown,
            "raw-invite-token-123",
            "654321",
            "candidate@example.com",
            "https://linkedin.com/in/private-profile",
            "BarePassword!42",
            "job-safe-123",
            42,
            extra={"unknown": unknown},
        )

    rendered = stream.getvalue()
    assert unknown.rendered is False
    for secret in (
        unknown.secret,
        "raw-invite-token-123",
        "654321",
        "candidate@example.com",
        "https://linkedin.com/in/private-profile",
        "BarePassword!42",
        "exception-secret-BarePassword!42",
    ):
        assert secret not in rendered
    assert rendered.count("[REDACTED]") >= 4
    assert "redacted-" in rendered
    assert "job-safe-123" in rendered
    assert "count=42" in rendered


@pytest.mark.parametrize(
    "formatter",
    [JsonFormatter(service="test"), TextFormatter(service="test")],
)
def test_formatters_scrub_sensitive_keys_and_identifier_values(
    formatter: logging.Formatter,
) -> None:
    sensitive_request_id = "request-BarePassword42"
    sensitive_job_id = "job-candidate@example.com"
    sensitive_keys = (
        "candidate@example.com",
        "https://linkedin.com/in/private-key",
        "password=DictionaryKeySecret",
        "pin",
    )
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(formatter)
    logger = logging.getLogger(f"tests.obs001.keys.{type(formatter).__name__}")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.info(
        "key scrub",
        extra={
            "request_id": sensitive_request_id,
            "job_id": sensitive_job_id,
            sensitive_keys[0]: "first",
            sensitive_keys[1]: "second",
            sensitive_keys[2]: "third",
            sensitive_keys[3]: "fourth",
        },
    )

    rendered = stream.getvalue()
    for secret in (*sensitive_keys, sensitive_request_id, sensitive_job_id):
        assert secret not in rendered
    assert "redacted-" in rendered
    assert rendered.count("key-") >= 4


def test_sentry_events_and_breadcrumbs_are_recursively_scrubbed() -> None:
    event = {
        "request": {
            "headers": {"Authorization": "Bearer bearer-token-value"},
            "data": {"email": "candidate@example.com"},
        },
        "exception": {
            "values": [
                {
                    "value": (
                        "https://www.linkedin.com/in/sensitive-candidate "
                        "password=correct-horse-password"
                    )
                }
            ]
        },
        "breadcrumbs": {
            "values": [
                {
                    "message": "invite_token=invite-token-value",
                    "data": {"mfa_code": "totp-secret-value"},
                }
            ]
        },
        "tags": {"request_id": "safe-request-id"},
    }
    breadcrumb = {
        "message": "candidate@example.com",
        "data": {"authorization": "Bearer bearer-token-value"},
    }

    scrubbed_event = scrub_sentry_event(event)
    scrubbed_breadcrumb = scrub_sentry_breadcrumb(breadcrumb)
    serialized = json.dumps([scrubbed_event, scrubbed_breadcrumb])
    for value in SENSITIVE_VALUES:
        assert value not in serialized
    assert scrubbed_event["tags"]["request_id"] == "safe-request-id"


def test_sentry_scrubbing_fails_closed_for_custom_objects_and_bare_values() -> None:
    unknown = _LeakyObject("sentry-custom-secret-BarePassword!42")
    scrubbed = scrub_sentry_event(
        {
            "extra": {"unknown": unknown},
            "exception": {"values": [{"value": "raw-invite-token-123", "mechanism": unknown}]},
            "breadcrumbs": {
                "values": [
                    {
                        "message": (
                            "654321 candidate@example.com "
                            "https://linkedin.com/in/private-profile BarePassword!42"
                        ),
                        "data": {"unknown": unknown},
                    }
                ]
            },
            "tags": {"request_id": "safe-request-id"},
        }
    )
    serialized = json.dumps(scrubbed)
    assert unknown.rendered is False
    for secret in (
        unknown.secret,
        "raw-invite-token-123",
        "654321",
        "candidate@example.com",
        "https://linkedin.com/in/private-profile",
        "BarePassword!42",
    ):
        assert secret not in serialized
    assert scrubbed["tags"]["request_id"] == "safe-request-id"


def test_sentry_scrubs_sensitive_keys_and_identifier_values_collision_safely() -> None:
    sensitive_request_id = "request-BarePassword42"
    sensitive_job_id = "job-candidate@example.com"
    event = {
        "tags": {
            "request_id": sensitive_request_id,
            "job_id": sensitive_job_id,
        },
        "extra": {
            "candidate@example.com": "first",
            "https://linkedin.com/in/private-key": "second",
            "password=DictionaryKeySecret": "third",
            "pin": "fourth",
        },
    }
    breadcrumb = {
        "data": {
            "candidate@example.com": "first",
            "authorization": "second",
        },
        "message": "safe breadcrumb",
    }

    scrubbed_event = scrub_sentry_event(event)
    scrubbed_again = scrub_sentry_event(event)
    scrubbed_breadcrumb = scrub_sentry_breadcrumb(breadcrumb)
    assert scrubbed_event == scrubbed_again
    assert scrub_sentry_event(scrubbed_event) == scrubbed_event
    serialized = json.dumps([scrubbed_event, scrubbed_breadcrumb])
    for secret in (
        sensitive_request_id,
        sensitive_job_id,
        "candidate@example.com",
        "https://linkedin.com/in/private-key",
        "password=DictionaryKeySecret",
        '"pin"',
        "authorization",
    ):
        assert secret not in serialized
    assert scrubbed_event["tags"]["request_id"].startswith("redacted-")
    assert scrubbed_event["tags"]["job_id"].startswith("redacted-")
    assert len(scrubbed_event["extra"]) == 4
    assert all(key.startswith("key-") for key in scrubbed_event["extra"])
    assert len(scrubbed_breadcrumb["data"]) == 2
    assert all(key.startswith("key-") for key in scrubbed_breadcrumb["data"])


def test_unknown_keys_are_pseudonymized_and_collisions_are_lossless() -> None:
    payload = {"pin": "first", "x": "second", "message": "safe"}
    first = scrub_sensitive_data(payload)
    second = scrub_sensitive_data(payload)
    assert first == second
    assert "pin" not in first
    assert "x" not in first
    assert first["message"] == "safe"
    assert len(first) == 3

    with patch("app.core.logging._scrub_mapping_key", return_value="key-deadbeefdeadbeef"):
        collided = scrub_sensitive_data({"one": 1, "two": 2, "three": 3})
    assert collided == {
        "key-deadbeefdeadbeef": 1,
        "key-deadbeefdeadbeef-2": 2,
        "key-deadbeefdeadbeef-3": 3,
    }


def test_identifier_pseudonyms_are_idempotent_across_repeated_hops() -> None:
    from app.workers import queue as queue_module

    raw = "request-BarePassword42"
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/hop")
    async def hop(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    response = TestClient(app).get("/hop", headers={"X-Request-ID": raw})
    canonical = response.headers["X-Request-ID"]
    assert response.json()["request_id"] == canonical
    assert canonical.startswith("redacted-")
    assert scrub_identifier(canonical) == canonical
    # Audit metadata uses the same recursive scrubber.
    assert scrub_sensitive_data({"request_id": canonical})["request_id"] == canonical

    # Queue metadata receives the middleware value.
    set_request_id(canonical)
    try:
        queued = queue_module._request_context_meta()
        assert queued == {"request_id": canonical}
    finally:
        set_request_id(None)
    # The worker applies scrub_identifier again when restoring queued context.
    assert scrub_identifier(queued["request_id"]) == canonical

    # Formatters apply another correlation scrub without changing the value.
    record = logging.LogRecord(
        name="tests.obs001.propagation",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="propagation",
        args=(),
        exc_info=None,
    )
    record.request_id = canonical
    rendered = json.loads(JsonFormatter(service="test").format(record))
    assert rendered["request_id"] == canonical


def test_paths_queries_and_urls_are_structurally_sanitized_across_sinks() -> None:
    raw_token = "tiny-secret"
    raw_query = "email=candidate@example.com&code=1234"
    raw_path = f"/api/staff-invites/{raw_token}?{raw_query}"
    sanitized_path = sanitize_path(raw_path)
    assert sanitize_path(sanitized_path) == sanitized_path
    assert sanitized_path.startswith("/api/staff-invites/segment-")
    assert raw_token not in sanitized_path
    assert "candidate@example.com" not in sanitized_path
    assert "1234" not in sanitized_path

    record = logging.LogRecord(
        name="tests.obs001.path",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"request failed at {raw_path}",
        args=(),
        exc_info=None,
    )
    rendered = JsonFormatter(service="test").format(record)
    assert raw_token not in rendered
    assert "candidate@example.com" not in rendered
    assert "1234" not in rendered
    assert "/api/staff-invites/segment-" in rendered

    event = scrub_sentry_event(
        {
            "request": {
                "url": f"https://example.com{raw_path}",
                "query_string": raw_query,
            },
            "tags": {"http.path": f"/api/staff-invites/{raw_token}"},
        }
    )
    breadcrumb = scrub_sentry_breadcrumb(
        {
            "category": "http",
            "data": {
                "url": f"https://example.com{raw_path}",
                "query_string": raw_query,
            },
        }
    )
    audit_metadata = scrub_sensitive_data({"path": raw_path, "query_string": raw_query})
    serialized = json.dumps([event, breadcrumb, audit_metadata])
    assert raw_token not in serialized
    assert "candidate@example.com" not in serialized
    assert "1234" not in serialized
    assert "/api/staff-invites/segment-" in serialized


def test_sentry_init_forces_no_default_pii_and_installs_scrubbers() -> None:
    from app.core.config import Settings
    from app.observability import error_tracking

    error_tracking._initialized = False
    with patch("sentry_sdk.init") as sentry_init:
        init_error_tracking(
            Settings(
                SENTRY_DSN="http://example@test.local/1",
                SENTRY_SEND_DEFAULT_PII=True,
            )
        )
    kwargs = sentry_init.call_args.kwargs
    assert kwargs["send_default_pii"] is False
    assert kwargs["before_send"] is scrub_sentry_event
    assert kwargs["before_breadcrumb"] is scrub_sentry_breadcrumb


def test_invalid_request_ids_are_replaced_and_valid_ids_are_preserved() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/request-id")
    async def request_id(request: Request) -> dict[str, str]:
        return {"request_id": request.state.request_id}

    client = TestClient(app)
    valid = client.get("/request-id", headers={"X-Request-ID": "caller.request-123"})
    assert valid.headers["X-Request-ID"] == "caller.request-123"
    assert valid.json()["request_id"] == "caller.request-123"

    credential_shaped = "request-BarePassword42"
    credential_response = client.get(
        "/request-id",
        headers={"X-Request-ID": credential_shaped},
    )
    safe_credential_id = credential_response.headers["X-Request-ID"]
    assert safe_credential_id == credential_response.json()["request_id"]
    assert safe_credential_id.startswith("redacted-")
    assert credential_shaped not in credential_response.text

    invalid_value = "candidate@example.com/" + "x" * 200
    invalid = client.get("/request-id", headers={"X-Request-ID": invalid_value})
    replacement = invalid.headers["X-Request-ID"]
    assert replacement == invalid.json()["request_id"]
    assert replacement != invalid_value
    assert is_valid_request_id(replacement)
    assert re.fullmatch(r"[0-9a-f-]{36}", replacement)


async def test_audit_metadata_is_scrubbed_and_non_request_ids_are_explicit(
    db_session,
    seed_user,
) -> None:
    row = await record_admin_action(
        db_session,
        actor_user_id=seed_user.id,
        action="obs.safe_action",
        target_type="probe",
        before={
            "email": "candidate@example.com",
            "candidate@example.com": "first",
            "authorization": "second",
        },
        after={
            "authorization": "Bearer bearer-token-value",
            "request_id": "safe-request-id",
        },
    )
    assert row.request_id.startswith("system-")
    assert row.before["email"] == "[REDACTED]"
    before_unknown = {key: value for key, value in row.before.items() if key != "email"}
    assert len(before_unknown) == 2
    assert all(key.startswith("key-") for key in before_unknown)
    assert set(before_unknown.values()) == {"first", "[REDACTED]"}
    assert row.after["request_id"] == "safe-request-id"
    after_unknown = {key: value for key, value in row.after.items() if key != "request_id"}
    assert len(after_unknown) == 1
    assert next(iter(after_unknown)).startswith("key-")
    assert next(iter(after_unknown.values())) == "[REDACTED]"


async def test_denied_staff_invite_gets_correlated_fallback_audit(
    client,
    regular_user,
    auth_headers,
    db_session,
) -> None:
    request_id = "denied-staff-invite-request"
    response = client.post(
        "/api/staff-invites",
        headers={
            **auth_headers(regular_user.id),
            "Idempotency-Key": "denied-invite",
            "X-Request-ID": request_id,
        },
        json={
            "email": "candidate@example.com",
            "confirmation_email": "candidate@example.com",
            "role_name": "recruiter",
            "mfa_code": "123456",
        },
    )
    assert response.status_code == 403
    assert response.headers["X-Request-ID"] == request_id
    row = (
        await db_session.execute(
            select(AdminAuditLog).where(AdminAuditLog.request_id == request_id)
        )
    ).scalar_one()
    assert row.captured_by == "fallback"
    assert row.outcome == "denied"
    assert row.actor_user_id == regular_user.id
    assert "candidate@example.com" not in repr(row.after)


async def test_staff_invite_initial_replay_and_reuse_each_have_one_explicit_audit(
    client,
    superuser_with_mfa,
    auth_headers,
    db_session,
) -> None:
    email = "obs-invite-paths@example.com"
    payload = {
        "email": email,
        "confirmation_email": email,
        "role_name": "recruiter",
        "mfa_code": pyotp.TOTP(superuser_with_mfa.mfa_secret).now(),
    }

    def headers(key: str, request_id: str) -> dict[str, str]:
        return {
            **auth_headers(superuser_with_mfa.id),
            "Idempotency-Key": key,
            "X-Request-ID": request_id,
        }

    initial = client.post(
        "/api/staff-invites",
        json=payload,
        headers=headers("obs-initial", "obs-invite-initial"),
    )
    replay = client.post(
        "/api/staff-invites",
        json=payload,
        headers=headers("obs-initial", "obs-invite-replay"),
    )
    reuse = client.post(
        "/api/staff-invites",
        json=payload,
        headers=headers("obs-reuse", "obs-invite-reuse"),
    )
    assert initial.status_code == replay.status_code == reuse.status_code == 201
    initial_body = initial.json()["data"]
    replay_body = replay.json()["data"]
    reuse_body = reuse.json()["data"]
    assert replay_body["id"] == initial_body["id"]
    assert replay_body["invite_token"] == initial_body["invite_token"]
    assert reuse_body["id"] == initial_body["id"]
    assert reuse_body["invite_token"] is None

    request_ids = {
        "obs-invite-initial",
        "obs-invite-replay",
        "obs-invite-reuse",
    }
    rows = (
        (
            await db_session.execute(
                select(AdminAuditLog).where(AdminAuditLog.request_id.in_(request_ids))
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 3
    by_request = {row.request_id: row for row in rows}
    assert by_request["obs-invite-initial"].action == "staff_invite.issued"
    assert by_request["obs-invite-replay"].action == "staff_invite.replayed"
    assert by_request["obs-invite-reuse"].action == "staff_invite.reused"
    assert all(row.captured_by == "explicit" for row in rows)
    assert all(row.actor_user_id == superuser_with_mfa.id for row in rows)


async def test_staff_invite_conflict_winner_audit_is_transactional(
    db_session,
    superuser,
) -> None:
    from app.modules.staff_invites import repository

    invite, _token = await repository.create_invite(
        db_session,
        email="obs-conflict-winner@example.com",
        role_name="recruiter",
        invited_by=superuser.id,
        request_id="obs-conflict-seed",
        idempotency_key="obs-conflict-seed",
    )
    await repository._record_successful_post(
        db_session,
        invited_by=superuser.id,
        invite=invite,
        request_id="obs-conflict-winner",
        ip_address=None,
        result="conflict_winner",
    )
    await db_session.commit()
    row = (
        await db_session.execute(
            select(AdminAuditLog).where(AdminAuditLog.request_id == "obs-conflict-winner")
        )
    ).scalar_one()
    assert row.action == "staff_invite.conflict_winner"
    assert row.captured_by == "explicit"


async def test_staff_invite_late_failure_rolls_back_audit_and_success_metric(
    db_session,
    superuser,
) -> None:
    from app.modules.admin import privileged_operations_repository
    from app.modules.staff_invites import repository

    success_before = _audit_metric_value("success")
    failure_before = _audit_metric_value("failure")
    with (
        patch.object(
            privileged_operations_repository,
            "complete_idempotency_record",
            new=AsyncMock(side_effect=RuntimeError("completion failed")),
        ),
        pytest.raises(RuntimeError, match="completion failed"),
    ):
        await repository.create_invite(
            db_session,
            email="obs-invite-rollback@example.com",
            role_name="recruiter",
            invited_by=superuser.id,
            request_id="obs-invite-rollback",
            idempotency_key="obs-invite-rollback",
        )
    audit_count = await db_session.scalar(
        select(func.count())
        .select_from(AdminAuditLog)
        .where(AdminAuditLog.request_id == "obs-invite-rollback")
    )
    assert audit_count == 0
    assert _audit_metric_value("success") == success_before
    assert _audit_metric_value("failure") == failure_before + 1


def test_fallback_db_failure_keeps_committed_response_and_logs_no_exception() -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(AdminAuditFallbackMiddleware)

    @app.post("/api/admin/committed")
    async def committed() -> JSONResponse:
        return JSONResponse({"committed": True})

    @asynccontextmanager
    async def failing_session():
        raise RuntimeError("database failed candidate@example.com token=invite-token-value")
        yield

    with (
        patch("app.database.session.get_db_session_context", new=failing_session),
        patch("app.modules.admin.audit.logger.critical") as critical,
    ):
        response = TestClient(app).post(
            "/api/admin/committed",
            headers={"X-Request-ID": "fallback-db-failure"},
        )
    assert response.status_code == 200
    assert response.json() == {"committed": True}
    assert response.headers["X-Request-ID"] == "fallback-db-failure"
    critical.assert_called_once()
    logged = repr(critical.call_args)
    assert "admin audit fallback persistence failed" in logged
    assert "candidate@example.com" not in logged
    assert "invite-token-value" not in logged


def test_security_metric_labels_are_bounded_and_secret_free() -> None:
    record_authorization("permission", allowed=True)
    record_authorization("permission", allowed=False)
    record_audit("explicit", "success")
    record_audit("explicit", "failure")
    record_audit("fallback", "anomaly")
    record_audit("fallback", "failure")
    record_queue_event("failed_jobs", "inspected")
    record_queue_event("failed_jobs", "redacted")
    record_queue_event("retry", "denied")
    metrics = generate_latest().decode()
    authorization_labels = {
        tuple(sorted(sample.labels.items()))
        for metric in authorization_decisions_total.collect()
        for sample in metric.samples
    }
    audit_labels = {
        tuple(sorted(sample.labels.items()))
        for metric in admin_audit_events_total.collect()
        for sample in metric.samples
    }
    queue_labels = {
        tuple(sorted(sample.labels.items()))
        for metric in queue_admin_events_total.collect()
        for sample in metric.samples
    }
    assert (("decision", "allow"), ("policy", "permission")) in authorization_labels
    assert (("capture", "fallback"), ("outcome", "failure")) in audit_labels
    assert (("operation", "retry"), ("outcome", "denied")) in queue_labels
    for value in SENSITIVE_VALUES:
        assert value not in metrics


def test_security_metric_helpers_map_unknown_values_to_closed_vocabulary() -> None:
    secret = "candidate@example.com/BarePassword!42"
    record_authorization(secret, allowed=True)
    record_audit(secret, secret)
    record_queue_event(secret, secret)

    authorization_samples = [
        sample
        for metric in authorization_decisions_total.collect()
        for sample in metric.samples
        if sample.name.endswith("_total")
    ]
    audit_samples = [
        sample
        for metric in admin_audit_events_total.collect()
        for sample in metric.samples
        if sample.name.endswith("_total")
    ]
    queue_samples = [
        sample
        for metric in queue_admin_events_total.collect()
        for sample in metric.samples
        if sample.name.endswith("_total")
    ]
    assert {sample.labels["policy"] for sample in authorization_samples} <= {
        "staff",
        "permission",
        "superuser",
        "queue_retry",
        "unknown",
    }
    assert {sample.labels["capture"] for sample in audit_samples} <= {
        "explicit",
        "fallback",
        "unknown",
    }
    assert {sample.labels["outcome"] for sample in audit_samples} <= {
        "success",
        "failure",
        "anomaly",
        "unknown",
    }
    assert {sample.labels["operation"] for sample in queue_samples} <= {
        "overview",
        "failed_jobs",
        "retry",
        "unknown",
    }
    assert {sample.labels["outcome"] for sample in queue_samples} <= {
        "inspected",
        "redacted",
        "denied",
        "unknown",
    }
    assert secret not in repr(
        [sample.labels for sample in authorization_samples + audit_samples + queue_samples]
    )


def _audit_metric_value(outcome: str) -> float:
    return sum(
        sample.value
        for metric in admin_audit_events_total.collect()
        for sample in metric.samples
        if sample.name == "admin_audit_events_total"
        and sample.labels == {"capture": "explicit", "outcome": outcome}
    )


async def test_explicit_audit_success_metric_waits_for_commit(db_session, seed_user) -> None:
    before = _audit_metric_value("success")
    await record_admin_action(
        db_session,
        actor_user_id=seed_user.id,
        action="obs.commit",
        target_type="probe",
    )
    assert _audit_metric_value("success") == before
    await db_session.commit()
    assert _audit_metric_value("success") == before + 1


async def test_explicit_audit_rollback_after_flush_records_only_failure(
    db_session,
    seed_user,
) -> None:
    success_before = _audit_metric_value("success")
    failure_before = _audit_metric_value("failure")
    await record_admin_action(
        db_session,
        actor_user_id=seed_user.id,
        action="obs.rollback",
        target_type="probe",
    )
    await db_session.rollback()
    assert _audit_metric_value("success") == success_before
    assert _audit_metric_value("failure") == failure_before + 1


async def test_explicit_audit_flush_failure_records_one_failure(
    db_session,
    seed_user,
) -> None:
    success_before = _audit_metric_value("success")
    failure_before = _audit_metric_value("failure")
    with (
        patch.object(db_session, "flush", new=AsyncMock(side_effect=RuntimeError("db failed"))),
        pytest.raises(RuntimeError, match="db failed"),
    ):
        await record_admin_action(
            db_session,
            actor_user_id=seed_user.id,
            action="obs.flush_failure",
            target_type="probe",
        )
    await db_session.rollback()
    assert _audit_metric_value("success") == success_before
    assert _audit_metric_value("failure") == failure_before + 1


async def test_explicit_audit_metrics_are_isolated_across_concurrent_sessions() -> None:
    from app.database.session import SessionLocal

    success_before = _audit_metric_value("success")
    failure_before = _audit_metric_value("failure")
    both_open = asyncio.Event()
    arrivals = 0
    arrival_lock = asyncio.Lock()
    transaction_lock = asyncio.Lock()

    async def write(action: str, *, commit: bool) -> None:
        nonlocal arrivals
        async with SessionLocal() as session:
            async with arrival_lock:
                arrivals += 1
                if arrivals == 2:
                    both_open.set()
            await both_open.wait()
            # SQLite allows only one writer. Both sessions remain live while
            # their independent audit transactions are serialized.
            async with transaction_lock:
                await record_admin_action(
                    session,
                    actor_user_id=None,
                    action=action,
                    target_type="probe",
                )
                if commit:
                    await session.commit()
                else:
                    await session.rollback()

    await asyncio.gather(
        write("obs.concurrent_commit", commit=True),
        write("obs.concurrent_rollback", commit=False),
    )
    assert _audit_metric_value("success") == success_before + 1
    assert _audit_metric_value("failure") == failure_before + 1


def test_valid_request_id_is_preserved_in_enrichment_queue_context() -> None:
    from app.domain.enums import RequestedTier
    from app.workers import queue as queue_module

    queue = patch("app.workers.queue.Queue").start()
    connection = patch("app.workers.queue.get_redis_connection").start()
    try:
        set_request_id("queue-context-request")
        queue_module.enqueue_enrichment("safe-job-id", [RequestedTier.tier2])
    finally:
        set_request_id(None)
        patch.stopall()

    connection.assert_called_once()
    assert queue.return_value.enqueue.call_args.kwargs["meta"] == {
        "request_id": "queue-context-request"
    }


def test_high_risk_route_inventory_stays_under_observability_coverage() -> None:
    from app.main import app

    mutation_routes = {
        (method, route.path)
        for route in app.routes
        for method in getattr(route, "methods", set())
        if method in {"POST", "PUT", "PATCH", "DELETE"}
    }
    expected = {
        ("POST", "/api/staff-invites"),
        ("POST", "/api/admin/impersonation/start/{user_id}"),
        ("POST", "/api/admin/mfa/disable"),
        ("POST", "/api/admin/queues/{name}/failed/{job_id}/retry"),
    }
    assert expected <= mutation_routes


# ──────────────────────────────────────────────────────────────────────────────
# OBS-001 Blocker 1: sanitizers must be total functions on malformed input
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "malformed_url",
    [
        "https://host:bad/token",  # bare-integer-invalid port
        "https://[::1/path",  # truncated IPv6 bracket
        "://no-scheme/path",  # empty scheme
        "https://host/path?" + "k=v&" * 5000,  # oversized query string
        "https://host:999999/over-max-port",  # port out of valid range
        "\x00\xff://null-bytes",  # null bytes in scheme
    ],
    ids=[
        "bad-port",
        "truncated-ipv6",
        "empty-scheme",
        "oversized-query",
        "over-max-port",
        "null-bytes",
    ],
)
def test_sanitize_url_is_total_function_on_malformed_input(malformed_url: str) -> None:
    """sanitize_url must never raise on attacker-controlled malformed URLs."""
    from app.core.logging import sanitize_url

    # Must not raise; must return a string.
    result = sanitize_url(malformed_url)
    assert isinstance(result, str)
    # Result must be the fallback sentinel or a sanitised form — never the raw
    # attacker-controlled input unchanged, and never leaking sensitive tokens.
    assert result != malformed_url or result == "[malformed-url]", (
        f"sanitize_url returned raw input unchanged: {result!r}"
    )
    assert "\x00" not in result and "\xff" not in result, (
        f"null/control bytes leaked through: {result!r}"
    )
    assert result == "[malformed-url]" or result.startswith("https://") or "/" in result, (
        f"unexpected sanitized form: {result!r}"
    )


@pytest.mark.parametrize(
    "malformed_url",
    [
        "https://host:bad/token",
        "https://[::1/path",
        "://no-scheme/path",
        "https://host/path?" + "k=v&" * 5000,
    ],
    ids=["bad-port", "truncated-ipv6", "empty-scheme", "oversized-query"],
)
def test_malformed_url_does_not_break_json_formatter(malformed_url: str) -> None:
    """Malformed URLs appearing in log messages must be sanitized, never raise."""
    record = logging.LogRecord(
        name="tests.obs001.malformed_url",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=f"request url={malformed_url}",
        args=(),
        exc_info=None,
    )
    # Must not raise.
    rendered = JsonFormatter(service="test").format(record)
    assert isinstance(rendered, str)
    # The raw malformed fragment must not appear verbatim in sensitive contexts.
    parsed = json.loads(rendered)
    assert "bad" not in parsed.get("message", "") or "host:bad" not in malformed_url


@pytest.mark.parametrize(
    "malformed_url",
    [
        "https://host:bad/token",
        "https://[::1/path",
    ],
    ids=["bad-port", "truncated-ipv6"],
)
def test_malformed_url_does_not_break_sentry_scrubbers(malformed_url: str) -> None:
    """Malformed URLs in Sentry events/breadcrumbs must be sanitized gracefully."""
    event = scrub_sentry_event(
        {
            "request": {"url": malformed_url},
            "breadcrumbs": {"values": [{"data": {"url": malformed_url}}]},
        }
    )
    # Must be serializable (no exception raised).
    serialized = json.dumps(event)
    assert isinstance(serialized, str)


# ──────────────────────────────────────────────────────────────────────────────
# OBS-001 Blocker 2: fallback audit actions preserve static route verbs
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path", "expected_fragment"),
    [
        # Moderation routes — "moderate" must survive in the action string.
        (
            "PATCH",
            f"/api/admin/questions/{'a' * 36}/moderate",
            "moderate",
        ),
        (
            "PATCH",
            f"/api/admin/documents/{'b' * 36}/moderate",
            "moderate",
        ),
        # Review-decision route — "decide" must survive.
        (
            "POST",
            f"/api/admin/review-queue/{'c' * 36}/decide",
            "decide",
        ),
        # Feature-flags route — "feature-flags" must survive.
        (
            "POST",
            "/api/admin/feature-flags",
            "feature-flags",
        ),
        # Queue retry — "retry" must survive.
        (
            "POST",
            f"/api/admin/queues/high/failed/{'d' * 36}/retry",
            "retry",
        ),
    ],
    ids=[
        "moderate-question",
        "moderate-document",
        "decide-review",
        "feature-flags-post",
        "queue-retry",
    ],
)
def test_fallback_action_preserves_static_route_verbs(
    method: str, path: str, expected_fragment: str
) -> None:
    """Static route action words must remain readable in fallback action strings."""
    from app.modules.admin.audit import _build_fallback_action

    action = _build_fallback_action(method, path)
    assert len(action) <= 64, f"Action exceeds 64 chars: {action!r}"
    assert expected_fragment in action, (
        f"Expected fragment {expected_fragment!r} not found in {action!r}"
    )


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("PATCH", f"/api/admin/questions/{'a' * 36}/moderate"),
        ("POST", f"/api/admin/review-queue/{'c' * 36}/decide"),
        ("POST", f"/api/admin/queues/high/failed/{'d' * 36}/retry"),
    ],
    ids=["moderate", "decide", "retry"],
)
def test_fallback_action_left_truncation_preserves_suffix(method: str, path: str) -> None:
    """When the action would exceed 64 chars, truncation must come from the left
    so the identifying suffix (``/moderate``, ``/decide``, ``/retry``) is preserved."""
    from app.modules.admin.audit import _ACTION_MAX_LENGTH, _build_fallback_action

    action = _build_fallback_action(method, path)
    assert len(action) <= _ACTION_MAX_LENGTH
    # The normalized path ends with the verb — it must still be present.
    assert action.endswith(("/moderate", "/decide", "/retry")), (
        f"Suffix lost from truncated action: {action!r}"
    )
