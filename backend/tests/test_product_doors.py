"""Focused staff-door route matrix and HTTP behavior tests."""

from __future__ import annotations

from collections.abc import Iterable
from uuid import uuid4

from fastapi.routing import APIRoute

from app.main import app, current_verified_user
from app.modules.admin import router as admin_router
from app.modules.admin.impersonation_router import router as impersonation_router
from app.modules.admin.mfa_router import router as mfa_router
from app.modules.admin.permissions import require_staff, user_is_staff
from app.modules.brands.assignment_router import router as recruiter_assignments_router
from app.modules.brands.deactivation_router import router as brand_deactivation_router
from app.modules.brands.router import router as brands_router
from app.modules.demand_intelligence.router import router as demand_intelligence_router
from app.modules.enrichment.router import router as enrich_router
from app.modules.linkedin_sourcing.router import router as linkedin_sourcing_router
from app.modules.outreach.linkedin_send_router import router as linkedin_send_router
from app.modules.signals.router import list_router as signals_list_router
from app.modules.staff_invites.router import router as staff_invites_router

STAFF_ROUTERS = (
    admin_router,
    brand_deactivation_router,
    brands_router,
    recruiter_assignments_router,
    enrich_router,
    demand_intelligence_router,
    linkedin_send_router,
    linkedin_sourcing_router,
    signals_list_router,
    staff_invites_router,
)


def _api_routes(routes: Iterable[object]) -> list[APIRoute]:
    return [route for route in routes if isinstance(route, APIRoute)]


def _route_endpoints(router) -> set[object]:
    return {route.endpoint for route in _api_routes(router.routes)}


def _direct_dependency_calls(route: APIRoute) -> set[object]:
    return {dependency.call for dependency in route.dependant.dependencies}


def test_require_staff_classifies_roleless_role_and_superuser(
    regular_user, support_user, superuser
) -> None:
    assert user_is_staff(regular_user) is False
    assert user_is_staff(support_user) is True
    assert user_is_staff(superuser) is True


def test_complete_router_matrix_has_no_extra_or_missing_staff_boundaries() -> None:
    expected_staff_endpoints = set().union(*(_route_endpoints(router) for router in STAFF_ROUTERS))
    app_routes = _api_routes(app.routes)
    actual_staff_endpoints = {
        route.endpoint for route in app_routes if require_staff in _direct_dependency_calls(route)
    }

    assert actual_staff_endpoints == expected_staff_endpoints


def test_mfa_and_whole_impersonation_router_are_independently_exempt() -> None:
    exempt_endpoints = _route_endpoints(mfa_router) | _route_endpoints(impersonation_router)
    assert exempt_endpoints.isdisjoint(_route_endpoints(admin_router))

    mounted_exempt_routes = [
        route for route in _api_routes(app.routes) if route.endpoint in exempt_endpoints
    ]
    assert {route.endpoint for route in mounted_exempt_routes} == exempt_endpoints
    for route in mounted_exempt_routes:
        dependency_calls = _direct_dependency_calls(route)
        assert current_verified_user in dependency_calls
        assert require_staff not in dependency_calls


def test_candidate_enrichment_is_blocked_by_staff_door(client, regular_user, auth_headers) -> None:
    response = client.get("/enrich", headers=auth_headers(regular_user.id))

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Staff access required"


def test_assigned_role_and_superuser_cross_staff_door(
    client, support_user, superuser, auth_headers
) -> None:
    for user in (support_user, superuser):
        response = client.get("/api/signals", headers=auth_headers(user.id))
        assert response.status_code == 200


def test_endpoint_rbac_still_returns_permission_specific_forbidden(
    client, support_user, auth_headers
) -> None:
    response = client.get(
        "/api/admin/feature-flags",
        headers=auth_headers(support_user.id),
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Missing permission: feature_flags:read"


def test_candidate_mfa_and_impersonation_status_end_remain_available(
    client, regular_user, auth_headers
) -> None:
    headers = auth_headers(regular_user.id)

    mfa_status = client.get("/api/admin/mfa/status", headers=headers)
    assert mfa_status.status_code == 200
    assert mfa_status.json()["data"]["mfa_enabled"] is False

    impersonation_status = client.get("/api/admin/impersonation/status", headers=headers)
    assert impersonation_status.status_code == 200
    assert impersonation_status.json()["data"]["is_impersonating"] is False

    end = client.post("/api/admin/impersonation/end", headers=headers)
    assert end.status_code == 400
    assert end.json()["error"]["message"] == "Not currently impersonating"


def test_candidate_impersonation_start_keeps_permission_gate(
    client, regular_user, auth_headers
) -> None:
    response = client.post(
        f"/api/admin/impersonation/start/{uuid4()}",
        headers=auth_headers(regular_user.id),
        json={"reason": "support investigation", "mfa_code": None},
    )

    assert response.status_code == 403
    assert response.json()["error"]["message"] == "Missing permission: impersonation:start"
