"""Frozen D-007 feature-flag read-only backend contract."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.routing import APIRoute
from sqlalchemy import select

from app.core.errors import AppError
from app.modules.admin.models import AdminAuditLog, FeatureFlag
from app.modules.admin.schemas import UpsertFeatureFlagRequest

READ_ONLY_MESSAGE = "Feature flag mutation is disabled until an application consumer exists."


async def test_authorized_read_remains_available(db_session, client, superuser, auth_headers):
    key = f"d007_read_{uuid4().hex}"
    db_session.add(
        FeatureFlag(
            key=key,
            enabled=False,
            value={"variant": "control"},
            description="administration-only metadata",
            updated_by=superuser.id,
        )
    )
    await db_session.commit()

    response = client.get(
        "/api/admin/feature-flags",
        headers=auth_headers(superuser.id),
    )

    assert response.status_code == 200
    matching = [flag for flag in response.json()["data"] if flag["key"] == key]
    assert len(matching) == 1
    assert matching[0]["enabled"] is False
    assert matching[0]["value"] == {"variant": "control"}


def test_unauthorized_reads_still_fail_closed(client, regular_user, support_user, auth_headers):
    expected_denials = (
        (regular_user, "Staff access required"),
        (support_user, "Missing permission: feature_flags:read"),
    )

    for user, expected_message in expected_denials:
        response = client.get(
            "/api/admin/feature-flags",
            headers=auth_headers(user.id),
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"
        assert response.json()["error"]["message"] == expected_message


def test_unauthenticated_read_remains_denied(client):
    response = client.get("/api/admin/feature-flags")

    assert response.status_code == 401
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/admin/feature-flags"),
        ("PUT", "/api/admin/feature-flags/auth_probe"),
        ("PATCH", "/api/admin/feature-flags/auth_probe"),
        ("DELETE", "/api/admin/feature-flags/auth_probe"),
    ],
)
def test_unauthenticated_mutations_are_denied_before_read_only_policy(client, method, path):
    response = client.request(method, path, json={"enabled": True})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/admin/feature-flags"),
        ("PUT", "/api/admin/feature-flags/auth_probe"),
        ("PATCH", "/api/admin/feature-flags/auth_probe"),
        ("DELETE", "/api/admin/feature-flags/auth_probe"),
    ],
)
def test_unauthorized_mutations_are_denied_before_read_only_policy(
    client, support_user, auth_headers, method, path
):
    response = client.request(
        method,
        path,
        json={"enabled": True},
        headers=auth_headers(support_user.id),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert response.json()["error"]["message"] == "Missing permission: feature_flags:write"


@pytest.mark.parametrize(
    ("request_kwargs",),
    [
        ({},),
        ({"content": b"{", "headers": {"Content-Type": "application/json"}},),
        ({"json": {"enabled": True, "value": {"variant": "b"}}},),
    ],
    ids=["missing-body", "malformed-body", "valid-body"],
)
def test_authorized_put_rejects_before_body_validation(
    client, superuser, auth_headers, request_kwargs
):
    headers = {**auth_headers(superuser.id), **request_kwargs.get("headers", {})}
    request_options = {key: value for key, value in request_kwargs.items() if key != "headers"}

    response = client.put(
        "/api/admin/feature-flags/body_validation_probe",
        headers=headers,
        **request_options,
    )

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "FEATURE_FLAGS_READ_ONLY"
    assert response.json()["error"]["message"] == READ_ONLY_MESSAGE


def test_disabled_mutations_have_no_success_response_or_request_body_contract(client):
    from app.modules.admin.flags_router import router

    mutation_routes = [
        route
        for route in router.routes
        if isinstance(route, APIRoute)
        and route.methods.intersection({"POST", "PUT", "PATCH", "DELETE"})
    ]

    assert {method for route in mutation_routes for method in route.methods} == {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }
    assert all(route.response_model is None for route in mutation_routes)
    assert all(route.status_code == 405 for route in mutation_routes)
    assert all(route.dependant.body_params == [] for route in mutation_routes)

    openapi_paths = client.app.openapi()["paths"]
    for route in mutation_routes:
        for method in route.methods:
            documented_responses = openapi_paths[route.path][method.lower()]["responses"]
            assert "405" in documented_responses
            assert not any(status_code.startswith("2") for status_code in documented_responses)


@pytest.mark.parametrize(
    ("method", "path_template", "json_body"),
    [
        ("POST", "/api/admin/feature-flags", {"key": "ignored", "enabled": True}),
        ("PUT", "/api/admin/feature-flags/{key}", {"enabled": True}),
        ("PATCH", "/api/admin/feature-flags/{key}", {"enabled": True}),
        ("DELETE", "/api/admin/feature-flags/{key}", None),
    ],
)
async def test_direct_backend_mutations_return_stable_read_only_error_without_state_change(
    db_session,
    client,
    superuser,
    auth_headers,
    method,
    path_template,
    json_body,
):
    key = f"d007_unchanged_{uuid4().hex}"
    flag = FeatureFlag(
        key=key,
        enabled=False,
        value={"variant": "control"},
        description="must remain unchanged",
        updated_by=superuser.id,
    )
    db_session.add(flag)
    await db_session.commit()
    original_updated_at = flag.updated_at

    response = client.request(
        method,
        path_template.format(key=key),
        json=json_body,
        headers=auth_headers(superuser.id),
    )

    assert response.status_code == 405
    assert response.json() == {
        "success": False,
        "error": {
            "code": "FEATURE_FLAGS_READ_ONLY",
            "message": READ_ONLY_MESSAGE,
            "details": None,
            "status_code": 405,
        },
        "meta": None,
    }

    db_session.expire_all()
    persisted = (
        await db_session.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    ).scalar_one()
    assert persisted.enabled is False
    assert persisted.value == {"variant": "control"}
    assert persisted.description == "must remain unchanged"
    assert persisted.updated_at.replace(tzinfo=None) == original_updated_at.replace(tzinfo=None)

    misleading_audit = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.action == "feature_flag.flipped",
            AdminAuditLog.target_id == key,
        )
    )
    assert misleading_audit.scalars().all() == []


async def test_rejected_post_cannot_create_submitted_key_and_fallback_records_denial(
    db_session, client, superuser, auth_headers
):
    key = f"d007_post_{uuid4().hex}"
    fallback_action = "post_/api/admin/feature-flags"
    baseline = await db_session.execute(
        select(AdminAuditLog.id).where(AdminAuditLog.action == fallback_action)
    )
    baseline_ids = set(baseline.scalars().all())

    response = client.post(
        "/api/admin/feature-flags",
        json={"key": key, "enabled": True, "description": "must not exist"},
        headers=auth_headers(superuser.id),
    )

    assert response.status_code == 405
    assert response.json()["error"]["code"] == "FEATURE_FLAGS_READ_ONLY"
    created = await db_session.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    assert created.scalar_one_or_none() is None

    fallback_result = await db_session.execute(
        select(AdminAuditLog).where(AdminAuditLog.action == fallback_action)
    )
    new_fallback_rows = [
        row for row in fallback_result.scalars().all() if row.id not in baseline_ids
    ]
    assert len(new_fallback_rows) == 1
    assert new_fallback_rows[0].captured_by == "fallback"
    assert new_fallback_rows[0].target_type == "unclassified"
    assert new_fallback_rows[0].after == {"status_code": 405}
    assert new_fallback_rows[0].outcome == "denied"

    success_audit = await db_session.execute(
        select(AdminAuditLog).where(
            AdminAuditLog.target_type == "feature_flag",
            AdminAuditLog.target_id == key,
        )
    )
    assert success_audit.scalars().all() == []


async def test_service_call_cannot_bypass_read_only_policy(db_session, superuser):
    key = f"d007_service_{uuid4().hex}"
    payload = UpsertFeatureFlagRequest(
        enabled=True,
        value={"variant": "treatment"},
        description="must not be created",
    )

    with (
        patch(
            "app.modules.admin.repository.get_feature_flag",
            new_callable=AsyncMock,
        ) as get_feature_flag,
        patch(
            "app.modules.admin.service.record_admin_action",
            new_callable=AsyncMock,
        ) as record_admin_action,
        pytest.raises(AppError) as exc_info,
    ):
        from app.modules.admin.service import upsert_feature_flag

        await upsert_feature_flag(
            db_session,
            actor_id=superuser.id,
            key=key,
            payload=payload,
            ip_address="127.0.0.1",
        )

    assert exc_info.value.code == "FEATURE_FLAGS_READ_ONLY"
    assert exc_info.value.status_code == 405
    assert exc_info.value.message == READ_ONLY_MESSAGE
    get_feature_flag.assert_not_awaited()
    record_admin_action.assert_not_awaited()

    result = await db_session.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    assert result.scalar_one_or_none() is None
