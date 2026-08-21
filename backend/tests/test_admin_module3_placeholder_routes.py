"""Module 3 (interview questions / practice audio) admin placeholder routes.

These stub routers (`app/modules/admin/questions_router.py`,
`app/modules/admin/practice_audio_router.py`) are NOT yet wired into
`app/modules/admin/__init__.py` (the real aggregator is held back and wired
centrally once all Batch-1 admin chunks land), so `app.main.app` does not
expose `/api/admin/questions` or `/api/admin/practice-audio` yet. This file
builds its own minimal FastAPI app that mounts just the two new routers
directly, wired with the same auth-override mechanism `tests/conftest.py`
uses for the real app (`test_auth_dependency` in place of
`get_current_user_from_cookie`), plus the same exception handlers as the real
app so `assert_error`'s envelope-shape assertions still hold.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user_from_cookie
from app.core.exception_handlers import register_exception_handlers
from app.modules.admin.practice_audio_router import router as practice_audio_router
from app.modules.admin.questions_router import router as questions_router
from tests.conftest import test_auth_dependency as _test_auth_dependency
from tests.envelope_helpers import assert_error

# NOTE: no module-level `pytestmark = pytest.mark.asyncio` here — this file
# mixes sync (`test_router_files_do_not_import_module3_app_code`) and async
# test functions, and pyproject.toml's asyncio_mode = "auto" already handles
# async def tests automatically (see tests/test_admin_rbac.py for the same
# convention and rationale).

_ROUTER_FILES = [
    Path(__file__).resolve().parents[1] / "app" / "modules" / "admin" / "questions_router.py",
    Path(__file__).resolve().parents[1] / "app" / "modules" / "admin" / "practice_audio_router.py",
]


@pytest.fixture
def module3_client():
    """Standalone app mounting only the two Module-3 placeholder routers.

    Does not touch `app.main.app` or `app/modules/admin/__init__.py` — those
    are out of scope for this chunk (the real aggregator wiring happens once
    all Batch-1 chunks land).
    """
    app = FastAPI()
    app.include_router(questions_router)
    app.include_router(practice_audio_router)
    register_exception_handlers(app)
    app.dependency_overrides[get_current_user_from_cookie] = _test_auth_dependency
    return TestClient(app)


QUESTIONS_ROUTES = [
    ("get", "/api/admin/questions", "questions", "read"),
    ("get", "/api/admin/questions/11111111-1111-1111-1111-111111111111", "questions", "read"),
    (
        "post",
        "/api/admin/questions/11111111-1111-1111-1111-111111111111/moderate",
        "questions",
        "moderate",
    ),
]

PRACTICE_AUDIO_ROUTES = [
    ("get", "/api/admin/practice-audio", "practice_audio", "read"),
    (
        "get",
        "/api/admin/practice-audio/11111111-1111-1111-1111-111111111111",
        "practice_audio",
        "read",
    ),
    (
        "post",
        "/api/admin/practice-audio/11111111-1111-1111-1111-111111111111/moderate",
        "practice_audio",
        "moderate",
    ),
]

ALL_ROUTES = QUESTIONS_ROUTES + PRACTICE_AUDIO_ROUTES


@pytest.mark.parametrize("method, path, resource, action", ALL_ROUTES)
async def test_placeholder_route_returns_501_for_authorized_user(
    module3_client, superuser, auth_headers, method, path, resource, action
):
    """Migration 041 grants `admin` every Module-3 permission, and
    `is_superuser` bypasses the RBAC lookup entirely (Decision 1), so a
    superuser always has the required permission. Every route must still
    respond 501 — not 404 (unmounted) and not 500 (crash) — once past the
    permission gate."""
    response = getattr(module3_client, method)(path, headers=auth_headers(superuser.id))
    body = assert_error(response, 501)
    assert "not yet merged" in body["error"]["message"]
    assert "feat/phase2-module3-interview-prep" in body["error"]["message"]


@pytest.mark.parametrize("method, path, resource, action", ALL_ROUTES)
async def test_placeholder_route_permission_gate_runs_before_501(
    module3_client, regular_user, auth_headers, method, path, resource, action
):
    """A user with no role and no `is_superuser` flag has none of the
    `questions:*`/`practice_audio:*` permissions (migration 041 only grants
    them to `admin` and, for `*:read`, `support`). RBAC must reject with 403
    *before* the handler body ever runs, so the placeholder never leaks a 501
    to an unauthorized caller."""
    response = getattr(module3_client, method)(path, headers=auth_headers(regular_user.id))
    assert_error(response, 403, code="FORBIDDEN")


async def test_placeholder_route_requires_authentication(module3_client):
    """No auth headers at all -> 401, same as every other admin route."""
    response = module3_client.get("/api/admin/questions")
    assert response.status_code == 401
    response = module3_client.get("/api/admin/practice-audio")
    assert response.status_code == 401


def test_router_files_do_not_import_module3_app_code():
    """Static check (per the plan's own scope note): neither new router file
    may import from any `app.modules.questions` / `app.modules.practice_audio`
    package, since no such module exists on this branch — the real Module 3
    feature is entirely on the unmerged `feat/phase2-module3-interview-prep`
    branch. This walks each file's AST import statements (not just a text
    grep) so a match couldn't hide in a string/comment or a differently
    formatted import.
    """
    forbidden_module_names = {"questions", "practice_audio"}

    for router_file in _ROUTER_FILES:
        tree = ast.parse(router_file.read_text(), filename=str(router_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".")[0]
                    assert top_level not in forbidden_module_names, (
                        f"{router_file.name} imports forbidden module {alias.name!r}"
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                parts = module.split(".")
                # Only `app.modules.<name>` segments count — `app.modules.admin`
                # (this file's own package) is fine.
                if len(parts) >= 3 and parts[0] == "app" and parts[1] == "modules":
                    assert parts[2] not in forbidden_module_names, (
                        f"{router_file.name} imports forbidden module {module!r}"
                    )
