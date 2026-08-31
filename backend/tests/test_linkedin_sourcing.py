"""Tests for the LinkedIn sourcing module (manual lead-entry only).

See task-orchestration/machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md
for the design rationale — this module backs a manual data-entry form filled
out by a human who read a LinkedIn profile themselves, never a scraper.

`linkedin_sourcing.router` is now registered in `app/main.py` (mounted
normally alongside the other routers, gated behind `current_verified_user`).
The guard below is a defensive no-op for this already-registered case — it
only registers the router a second time if some other test run has torn
down and rebuilt `app` without it, so this module's tests stay independent
of import order without ever double-mounting the router on the normal path.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi import Depends, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app, current_verified_user
from app.modules.documents.models import CvChatSession
from app.modules.linkedin_sourcing import repository, service
from app.modules.linkedin_sourcing import router as router_module
from app.modules.linkedin_sourcing.models import SourcedCandidateLead
from app.modules.linkedin_sourcing.router import router as linkedin_sourcing_router
from app.modules.linkedin_sourcing.schemas import CreateSourcedLeadRequest, ReviewSourcedLeadRequest

if not any(getattr(route, "path", "").startswith("/api/linkedin-sourcing") for route in app.routes):
    app.include_router(linkedin_sourcing_router, dependencies=[Depends(current_verified_user)])


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _valid_body(**overrides) -> CreateSourcedLeadRequest:
    defaults = {
        "full_name": "Jane Candidate",
        "headline": "Senior Backend Engineer",
        "location": "Berlin, Germany",
        "linkedin_profile_url": "https://www.linkedin.com/in/jane-candidate",
        "target_role": "Backend Engineer",
        "notes": "Strong distributed systems background.",
    }
    defaults.update(overrides)
    return CreateSourcedLeadRequest(**defaults)


# ---------------------------------------------------------------------------
# service.create_lead
# ---------------------------------------------------------------------------


async def test_create_lead_requires_sourced_by(db):
    with pytest.raises(HTTPException) as exc_info:
        await service.create_lead(db, sourced_by=None, body=_valid_body())
    assert exc_info.value.status_code == 401


async def test_create_lead_rejects_non_linkedin_url(db, regular_user):
    with pytest.raises(HTTPException) as exc_info:
        await service.create_lead(
            db,
            sourced_by=regular_user.id,
            body=_valid_body(linkedin_profile_url="https://example.com/in/jane-candidate"),
        )
    assert exc_info.value.status_code == 422


async def test_create_lead_success(db, regular_user):
    result = await service.create_lead(db, sourced_by=regular_user.id, body=_valid_body())
    assert result.full_name == "Jane Candidate"
    assert result.sourced_by == regular_user.id
    assert result.status == "new"
    assert result.linkedin_profile_url == "https://www.linkedin.com/in/jane-candidate"


# ---------------------------------------------------------------------------
# service.list_leads — shared, non-access-restrictive queue
# ---------------------------------------------------------------------------


async def test_list_leads_returns_leads_from_different_sourced_by_users(
    db, regular_user, seed_user
):
    await service.create_lead(
        db,
        sourced_by=regular_user.id,
        body=_valid_body(
            full_name="Lead One", linkedin_profile_url="https://www.linkedin.com/in/one"
        ),
    )
    await service.create_lead(
        db,
        sourced_by=seed_user.id,
        body=_valid_body(
            full_name="Lead Two", linkedin_profile_url="https://www.linkedin.com/in/two"
        ),
    )

    leads = await service.list_leads(db)
    names = {lead.full_name for lead in leads}
    assert {"Lead One", "Lead Two"}.issubset(names)
    sourced_by_ids = {lead.sourced_by for lead in leads}
    assert regular_user.id in sourced_by_ids
    assert seed_user.id in sourced_by_ids


async def test_list_leads_filters_by_status(db, regular_user):
    new_lead = await service.create_lead(
        db,
        sourced_by=regular_user.id,
        body=_valid_body(
            full_name="Status Filter New",
            linkedin_profile_url="https://www.linkedin.com/in/status-filter-new",
        ),
    )
    reviewed_lead = await service.create_lead(
        db,
        sourced_by=regular_user.id,
        body=_valid_body(
            full_name="Status Filter Reviewed",
            linkedin_profile_url="https://www.linkedin.com/in/status-filter-reviewed",
        ),
    )
    await service.review_lead(
        db,
        lead_id=reviewed_lead.id,
        reviewer_id=regular_user.id,
        body=ReviewSourcedLeadRequest(status="reviewed"),
    )

    reviewed_only = await service.list_leads(db, status="reviewed")
    reviewed_ids = {lead.id for lead in reviewed_only}
    assert reviewed_lead.id in reviewed_ids
    assert new_lead.id not in reviewed_ids


# ---------------------------------------------------------------------------
# service.review_lead
# ---------------------------------------------------------------------------


async def test_review_lead_updates_status_reviewed_by_and_reviewed_at(db, regular_user, seed_user):
    lead = await service.create_lead(db, sourced_by=regular_user.id, body=_valid_body())

    result = await service.review_lead(
        db,
        lead_id=lead.id,
        reviewer_id=seed_user.id,
        body=ReviewSourcedLeadRequest(status="contacted"),
    )

    assert result.status == "contacted"
    stored = await repository.get_by_id(db, lead.id)
    assert stored.reviewed_by == seed_user.id
    assert stored.reviewed_at is not None


async def test_review_lead_404_for_missing_lead(db, seed_user):
    with pytest.raises(HTTPException) as exc_info:
        await service.review_lead(
            db,
            lead_id=uuid4(),
            reviewer_id=seed_user.id,
            body=ReviewSourcedLeadRequest(status="dismissed"),
        )
    assert exc_info.value.status_code == 404


def test_review_request_schema_rejects_invalid_status():
    with pytest.raises(ValidationError):
        ReviewSourcedLeadRequest(status="not-a-real-status")


# ---------------------------------------------------------------------------
# HTTP-level: permission gating (POST endpoints require linkedin_sourcing:write)
# ---------------------------------------------------------------------------


def _auth_headers(user_id: str) -> dict[str, str]:
    from app.core.config import get_settings

    settings = get_settings()
    return {"Authorization": f"Bearer {settings.api_token}", "X-Test-User-ID": user_id}


def _run(coro):
    """Run an async db-layer call from inside a sync test that also needs the
    synchronous `TestClient` fixture (mirrors how the session-scoped
    `event_loop` fixture in conftest.py drives async fixtures for sync tests;
    no loop is actively running at this point in the test body, so this is
    safe, unlike calling it from inside an async test function)."""
    import asyncio

    return asyncio.get_event_loop().run_until_complete(coro)


def test_create_lead_endpoint_403s_without_permission(client: TestClient, regular_user):
    response = client.post(
        "/api/linkedin-sourcing/leads",
        headers=_auth_headers(str(regular_user.id)),
        json={
            "full_name": "Jane Candidate",
            "linkedin_profile_url": "https://www.linkedin.com/in/jane-candidate",
        },
    )
    from tests.envelope_helpers import assert_error

    assert_error(response, 403)


def test_create_lead_endpoint_succeeds_for_superuser(client: TestClient, superuser):
    response = client.post(
        "/api/linkedin-sourcing/leads",
        headers=_auth_headers(str(superuser.id)),
        json={
            "full_name": "Jane Candidate",
            "linkedin_profile_url": "https://www.linkedin.com/in/jane-candidate",
        },
    )
    from tests.envelope_helpers import assert_success

    data = assert_success(response)
    assert data["full_name"] == "Jane Candidate"
    assert data["status"] == "new"


def test_list_leads_endpoint_requires_write_permission(client: TestClient, regular_user):
    """`list_leads` requires ``linkedin_sourcing:write`` (same as create/review)."""
    response = client.get(
        "/api/linkedin-sourcing/leads", headers=_auth_headers(str(regular_user.id))
    )
    from tests.envelope_helpers import assert_error

    assert_error(response, 403)


def test_list_leads_endpoint_allows_superuser(client: TestClient, superuser):
    response = client.get("/api/linkedin-sourcing/leads", headers=_auth_headers(str(superuser.id)))
    from tests.envelope_helpers import assert_success

    assert_success(response)


# ---------------------------------------------------------------------------
# Design-boundary check: zero LinkedIn network calls / forbidden imports
# (release-blocking per the plan's Release-blocking review boundaries section)
# ---------------------------------------------------------------------------

_MODULE_DIR = Path(inspect.getfile(SourcedCandidateLead)).parent
_FORBIDDEN_IMPORT_SUBSTRINGS = (
    "app.integrations.linkedin",
    "app.integrations.multilogin.profile_pool",
)
_FORBIDDEN_HTTP_CLIENT_NAMES = ("requests", "httpx", "playwright", "selenium", "aiohttp")


def test_module_has_no_forbidden_imports_or_http_clients():
    """No import of app.integrations.linkedin / app.integrations.multilogin.profile_pool,
    and no HTTP-client/browser-automation library import anywhere in this
    module's source — the entire feature surface is a plain CRUD form over
    SourcedCandidateLead with zero network calls to any third-party site."""
    py_files = sorted(_MODULE_DIR.glob("*.py"))
    assert py_files, "expected linkedin_sourcing module files to exist"

    for path in py_files:
        source = path.read_text()
        for forbidden in _FORBIDDEN_IMPORT_SUBSTRINGS:
            assert forbidden not in source, f"{path.name} imports forbidden module {forbidden}"
        for lib in _FORBIDDEN_HTTP_CLIENT_NAMES:
            assert f"import {lib}" not in source, f"{path.name} imports forbidden HTTP client {lib}"
            assert f"from {lib}" not in source, f"{path.name} imports forbidden HTTP client {lib}"


def test_router_and_service_reexport_expected_symbols():
    """Sanity check that the module wiring (router -> service -> repository)
    is intact and importable end-to-end."""
    assert router_module.router is linkedin_sourcing_router
    assert callable(service.create_lead)
    assert callable(service.list_leads)
    assert callable(service.review_lead)


# ---------------------------------------------------------------------------
# service.mark_lead_converted / POST .../convert — Qualification path:
# SourcedCandidateLead -> User (see 12-linkedin-sourcing-intern-multilogin.md)
# ---------------------------------------------------------------------------


async def _make_candidate_document(db, user_id):
    from app.modules.documents.models import CandidateDocument

    doc = CandidateDocument(
        id=uuid4(),
        user_id=user_id,
        document_type="cv",
        original_filename="cv.pdf",
        storage_path="documents/x/y.pdf",
        file_hash=f"conversion-{uuid4().hex}",
        file_size_bytes=1000,
        raw_text="Jane Doe",
        extracted_data={},
        processing_status="completed",
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)
    return doc


async def _make_cv_chat_session(db, user_id, *, status: str):
    from datetime import UTC, datetime

    document = await _make_candidate_document(db, user_id)
    session = CvChatSession(
        id=uuid4(),
        user_id=user_id,
        document_id=document.id,
        status=status,
        missing_fields_at_start=[],
        fields_resolved=[],
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC) if status == "completed" else None,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


async def test_mark_lead_converted_sets_columns_and_preserves_status(db, regular_user, seed_user):
    lead = await service.create_lead(db, sourced_by=regular_user.id, body=_valid_body())
    await service.review_lead(
        db,
        lead_id=lead.id,
        reviewer_id=regular_user.id,
        body=ReviewSourcedLeadRequest(status="dismissed"),
    )
    await _make_cv_chat_session(db, seed_user.id, status="completed")

    result = await service.mark_lead_converted(db, lead_id=lead.id, user_id=seed_user.id)

    assert result.converted_user_id == seed_user.id
    assert result.converted_at is not None
    assert result.status == "dismissed"

    stored = await repository.get_by_id(db, lead.id)
    assert stored.converted_user_id == seed_user.id
    assert stored.converted_at is not None
    assert stored.status == "dismissed"


async def test_mark_lead_converted_409_if_target_user_not_qualified(db, regular_user, seed_user):
    lead = await service.create_lead(db, sourced_by=regular_user.id, body=_valid_body())
    await _make_cv_chat_session(db, seed_user.id, status="active")

    with pytest.raises(HTTPException) as exc_info:
        await service.mark_lead_converted(db, lead_id=lead.id, user_id=seed_user.id)
    assert exc_info.value.status_code == 409


async def test_mark_lead_converted_409_if_target_user_has_no_session(db, regular_user, seed_user):
    lead = await service.create_lead(db, sourced_by=regular_user.id, body=_valid_body())

    with pytest.raises(HTTPException) as exc_info:
        await service.mark_lead_converted(db, lead_id=lead.id, user_id=seed_user.id)
    assert exc_info.value.status_code == 409


async def test_mark_lead_converted_succeeds_when_target_user_qualified(db, regular_user, seed_user):
    lead = await service.create_lead(db, sourced_by=regular_user.id, body=_valid_body())
    await _make_cv_chat_session(db, seed_user.id, status="completed")

    result = await service.mark_lead_converted(db, lead_id=lead.id, user_id=seed_user.id)
    assert result.converted_user_id == seed_user.id


async def test_mark_lead_converted_404_for_missing_lead(db, seed_user):
    await _make_cv_chat_session(db, seed_user.id, status="completed")
    with pytest.raises(HTTPException) as exc_info:
        await service.mark_lead_converted(db, lead_id=uuid4(), user_id=seed_user.id)
    assert exc_info.value.status_code == 404


def test_convert_lead_endpoint_403s_without_permission(client: TestClient, regular_user):
    response = client.post(
        f"/api/linkedin-sourcing/leads/{uuid4()}/convert",
        headers=_auth_headers(str(regular_user.id)),
        json={"user_id": str(uuid4())},
    )
    from tests.envelope_helpers import assert_error

    assert_error(response, 403)


def test_convert_lead_endpoint_succeeds_for_superuser(client: TestClient, superuser, db):
    lead = _run(service.create_lead(db, sourced_by=superuser.id, body=_valid_body()))
    target_session = _run(_make_cv_chat_session(db, superuser.id, status="completed"))

    response = client.post(
        f"/api/linkedin-sourcing/leads/{lead.id}/convert",
        headers=_auth_headers(str(superuser.id)),
        json={"user_id": str(target_session.user_id)},
    )
    from tests.envelope_helpers import assert_success

    data = assert_success(response)
    assert data["converted_user_id"] == str(superuser.id)


async def test_converted_leads_remain_visible_via_list_leads(db, regular_user, seed_user):
    lead = await service.create_lead(
        db,
        sourced_by=regular_user.id,
        body=_valid_body(
            full_name="Convertible Lead",
            linkedin_profile_url="https://www.linkedin.com/in/convertible-lead",
        ),
    )
    await service.review_lead(
        db,
        lead_id=lead.id,
        reviewer_id=regular_user.id,
        body=ReviewSourcedLeadRequest(status="reviewed"),
    )
    await _make_cv_chat_session(db, seed_user.id, status="completed")
    await service.mark_lead_converted(db, lead_id=lead.id, user_id=seed_user.id)

    all_leads = await service.list_leads(db)
    assert lead.id in {item.id for item in all_leads}

    reviewed_only = await service.list_leads(db, status="reviewed")
    assert lead.id in {item.id for item in reviewed_only}

    refetched = await repository.get_by_id(db, lead.id)
    assert refetched.converted_user_id == seed_user.id
    assert refetched.converted_at is not None
    assert refetched.status == "reviewed"
