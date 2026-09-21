"""CTR-PRIV catalog completeness and fail-closed unclassified operations."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import AppError
from app.modules.admin.privileged_operations import (
    EXPECTED_PRIVILEGED_ROUTE_OPERATIONS,
    PRIVILEGED_OPERATION_CATALOG,
    assert_operation_available,
    get_operation_spec,
)

APP_ROOT = Path(__file__).resolve().parents[1] / "app"

ROUTER_HELPER_FILES = (
    APP_ROOT / "modules/admin/impersonation_router.py",
    APP_ROOT / "modules/admin/mfa_router.py",
    APP_ROOT / "modules/staff_invites/router.py",
    APP_ROOT / "modules/admin/users_router.py",
    APP_ROOT / "modules/admin/roles_router.py",
    APP_ROOT / "modules/admin/flags_router.py",
    APP_ROOT / "modules/admin/queues_router.py",
)

UNAVAILABLE_OPERATIONS = tuple(
    spec.operation_id
    for spec in PRIVILEGED_OPERATION_CATALOG.values()
    if spec.level == "UNAVAILABLE"
)


def test_catalog_ids_match_route_map() -> None:
    catalog_ids = set(PRIVILEGED_OPERATION_CATALOG)
    route_ids = {op for ops in EXPECTED_PRIVILEGED_ROUTE_OPERATIONS.values() for op in ops}
    assert catalog_ids == route_ids


def test_unclassified_operation_fails_closed() -> None:
    with pytest.raises(AppError) as exc:
        get_operation_spec("not.a.real.op")
    assert exc.value.status_code == 405
    assert exc.value.code == "PRIVILEGED_OPERATION_UNCLASSIFIED"


@pytest.mark.parametrize("operation_id", UNAVAILABLE_OPERATIONS)
def test_unavailable_operations_fail_closed(operation_id: str) -> None:
    with pytest.raises(AppError) as exc:
        assert_operation_available(operation_id)
    assert exc.value.status_code == 405


def test_identity_and_invite_routers_call_catalog_helpers() -> None:
    impersonation = (APP_ROOT / "modules/admin/impersonation_router.py").read_text()
    mfa = (APP_ROOT / "modules/admin/mfa_router.py").read_text()
    invites = (APP_ROOT / "modules/staff_invites/router.py").read_text()
    assert "require_idempotency_key" in impersonation
    assert '"impersonation.started"' in impersonation
    assert '"impersonation.ended"' in impersonation
    assert "require_idempotency_key" in mfa
    assert '"mfa.enrollment_started"' in mfa
    assert '"mfa.enrollment_confirmed"' in mfa
    assert '"mfa.disabled"' in mfa
    assert "assert_operation_available" in invites
    assert '"staff_invite.issued"' in invites


def test_catalogued_routes_have_helper_call_sites() -> None:
    sources = "\n".join(path.read_text() for path in ROUTER_HELPER_FILES)
    for operation_id in (
        "impersonation.started",
        "impersonation.ended",
        "mfa.enrollment_started",
        "staff_invite.issued",
        "user.role.assign",
        "role.create",
        "feature_flags.mutate",
        "queues.retry_failed_job",
    ):
        assert f'"{operation_id}"' in sources


@pytest.mark.asyncio
async def test_unavailable_http_routes_stay_405(client, superuser, auth_headers) -> None:
    headers = {
        **auth_headers(superuser.id),
        "Idempotency-Key": "catalog-unavailable-1",
    }
    assign = client.put(
        f"/api/admin/users/{superuser.id}/role",
        json={"role_id": None},
        headers=headers,
    )
    create_role = client.post(
        "/api/admin/roles",
        json={"name": "custom-blocked", "description": None},
        headers=headers,
    )
    deactivate = client.patch(
        f"/api/admin/users/{superuser.id}/status",
        json={"is_active": False, "reason": "should stay unavailable"},
        headers=headers,
    )
    flags = client.put(
        "/api/admin/feature-flags/blocked",
        json={"enabled": True},
        headers=headers,
    )
    retry = client.post(
        "/api/admin/queues/default/failed/job-1/retry",
        headers=headers,
    )
    assert assign.status_code == 405
    assert create_role.status_code == 405
    assert deactivate.status_code == 405
    assert flags.status_code == 405
    assert flags.json()["error"]["code"] == "FEATURE_FLAGS_READ_ONLY"
    assert retry.status_code == 405
    assert retry.json()["error"]["code"] == "QUEUE_ADMIN_READ_ONLY"
