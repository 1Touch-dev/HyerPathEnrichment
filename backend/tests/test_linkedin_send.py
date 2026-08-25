"""Tests for the LinkedIn send task queue (manual mode) and the operator-triggered
automated-batch mode (machine-2/06). See
task-orchestration/machine-2-parallel-tracks/06-linkedin-outreach-send.md and the
plan's "Track 06 — updated scope" section for the design rationale: this is a
human-in-the-loop task queue by default, and the batch mode still requires a human
to explicitly start it and caps sends with a hard per-day ceiling.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.auth.models import User
from app.main import app
from app.modules.outreach import linkedin_send_service
from app.modules.outreach.linkedin_send_models import LinkedInSendBatch, LinkedInSendTask
from app.modules.outreach.linkedin_send_schemas import CreateLinkedInSendBatchRequest
from app.modules.outreach.models import OutreachMessage
from app.workers.tasks.linkedin_send_batch import (
    LinkedInSendNotImplementedError,
    _run_linkedin_send_batch_job,
    _sends_today_for_profile,
)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _auth_headers(user_id: str) -> dict[str, str]:
    from app.core.config import get_settings

    settings = get_settings()
    return {"Authorization": f"Bearer {settings.api_token}", "X-Test-User-ID": user_id}


@pytest.fixture
async def test_user(db):
    user = User(
        id=uuid4(),
        email=f"linkedin-send-{uuid4().hex[:8]}@example.com",
        first_name="Jane",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _make_message(db, user_id, **overrides) -> OutreachMessage:
    defaults = {
        "id": uuid4(),
        "user_id": user_id,
        "company_name": "Acme",
        "subject": "Hi",
        "body": "Body",
        "status": "draft",
        "message_type": "linkedin",
        "recipient_linkedin_url": "https://www.linkedin.com/in/jane-recruiter",
    }
    defaults.update(overrides)
    message = OutreachMessage(**defaults)
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


# ---------------------------------------------------------------------------
# linkedin_send_service.enqueue_send_task
# ---------------------------------------------------------------------------


async def test_enqueue_send_task_creates_pending_task(db, test_user):
    message = await _make_message(db, test_user.id)
    task = await linkedin_send_service.enqueue_send_task(
        db,
        outreach_message_id=message.id,
        linkedin_profile_url=message.recipient_linkedin_url,
        action_type="direct_message",
    )
    assert task.status == "pending"
    assert task.batch_id is None
    assert task.outreach_message_id == message.id


async def test_enqueue_send_task_rejects_suppressed_profile_url(db, test_user):
    from app.compliance.suppression import add_suppression

    suppressed_url = "https://www.linkedin.com/in/blocked-recruiter"
    await add_suppression(db, suppressed_url, reason="opted out")
    message = await _make_message(db, test_user.id, recipient_linkedin_url=suppressed_url)

    with pytest.raises(HTTPException) as exc_info:
        await linkedin_send_service.enqueue_send_task(
            db,
            outreach_message_id=message.id,
            linkedin_profile_url=suppressed_url,
            action_type="direct_message",
        )
    assert exc_info.value.status_code == 403


# ---------------------------------------------------------------------------
# linkedin_send_service.claim_task / complete_task / skip_task — manual mode,
# batch_id IS NULL. These must behave exactly as before batch mode was added
# (regression coverage for the plan's explicit regression requirement).
# ---------------------------------------------------------------------------


async def test_claim_task_sets_claimed_status_and_operator(db, test_user):
    message = await _make_message(db, test_user.id)
    task = await linkedin_send_service.enqueue_send_task(
        db,
        outreach_message_id=message.id,
        linkedin_profile_url=message.recipient_linkedin_url,
        action_type="direct_message",
    )
    claimed = await linkedin_send_service.claim_task(db, task_id=task.id, operator_id=test_user.id)
    assert claimed.status == "claimed"
    assert claimed.claimed_by == test_user.id
    assert claimed.claimed_at is not None


async def test_claim_task_409s_when_claimed_by_another_operator(db, test_user, seed_user):
    message = await _make_message(db, test_user.id)
    task = await linkedin_send_service.enqueue_send_task(
        db,
        outreach_message_id=message.id,
        linkedin_profile_url=message.recipient_linkedin_url,
        action_type="direct_message",
    )
    await linkedin_send_service.claim_task(db, task_id=task.id, operator_id=test_user.id)

    with pytest.raises(HTTPException) as exc_info:
        await linkedin_send_service.claim_task(db, task_id=task.id, operator_id=seed_user.id)
    assert exc_info.value.status_code == 409


async def test_complete_task_with_batch_id_null_marks_parent_message_sent(db, test_user):
    """A task with batch_id IS NULL (manual mode) must keep working exactly as
    before batch mode was added — explicit regression test called out in the
    dispatch instructions."""
    message = await _make_message(db, test_user.id)
    task = await linkedin_send_service.enqueue_send_task(
        db,
        outreach_message_id=message.id,
        linkedin_profile_url=message.recipient_linkedin_url,
        action_type="direct_message",
    )
    assert task.batch_id is None

    completed = await linkedin_send_service.complete_task(
        db, task_id=task.id, operator_id=test_user.id, outcome_note="sent it"
    )
    assert completed.status == "completed"
    assert completed.completed_at is not None
    assert completed.outcome_note == "sent it"

    await db.refresh(message)
    assert message.status == "sent"
    assert message.sent_at is not None


async def test_skip_task_leaves_parent_message_draft(db, test_user):
    message = await _make_message(db, test_user.id)
    task = await linkedin_send_service.enqueue_send_task(
        db,
        outreach_message_id=message.id,
        linkedin_profile_url=message.recipient_linkedin_url,
        action_type="direct_message",
    )
    skipped = await linkedin_send_service.skip_task(
        db, task_id=task.id, operator_id=test_user.id, outcome_note="profile gone"
    )
    assert skipped.status == "skipped"

    await db.refresh(message)
    assert message.status == "draft"


async def test_complete_task_404_for_missing_task(db, test_user):
    with pytest.raises(HTTPException) as exc_info:
        await linkedin_send_service.complete_task(
            db, task_id=uuid4(), operator_id=test_user.id, outcome_note=None
        )
    assert exc_info.value.status_code == 404


async def test_complete_task_409_when_already_completed(db, test_user):
    message = await _make_message(db, test_user.id)
    task = await linkedin_send_service.enqueue_send_task(
        db,
        outreach_message_id=message.id,
        linkedin_profile_url=message.recipient_linkedin_url,
        action_type="direct_message",
    )
    await linkedin_send_service.complete_task(
        db, task_id=task.id, operator_id=test_user.id, outcome_note=None
    )
    with pytest.raises(HTTPException) as exc_info:
        await linkedin_send_service.complete_task(
            db, task_id=task.id, operator_id=test_user.id, outcome_note=None
        )
    assert exc_info.value.status_code == 409


# ---------------------------------------------------------------------------
# linkedin_send_service.create_batch / start_batch
# ---------------------------------------------------------------------------


async def test_create_batch_requires_positive_max_sends_per_day(db, test_user):
    with pytest.raises(HTTPException) as exc_info:
        await linkedin_send_service.create_batch(
            db,
            triggered_by=test_user.id,
            multilogin_profile_id="profile-1",
            max_sends_per_day=0,
            task_ids=[],
        )
    assert exc_info.value.status_code == 422


def test_create_batch_request_schema_rejects_missing_max_sends_per_day():
    """`max_sends_per_day` is required (no default) — omitting it must 422 at the
    Pydantic schema layer, per the release-blocking requirement."""
    with pytest.raises(ValidationError):
        CreateLinkedInSendBatchRequest(multilogin_profile_id="profile-1")


async def test_create_batch_attaches_existing_unbatched_tasks(db, test_user):
    message = await _make_message(db, test_user.id)
    task = await linkedin_send_service.enqueue_send_task(
        db,
        outreach_message_id=message.id,
        linkedin_profile_url=message.recipient_linkedin_url,
        action_type="direct_message",
    )
    batch = await linkedin_send_service.create_batch(
        db,
        triggered_by=test_user.id,
        multilogin_profile_id="profile-1",
        max_sends_per_day=10,
        task_ids=[task.id],
    )
    await db.refresh(task)
    assert task.batch_id == batch.id
    assert batch.status == "pending"


async def test_create_batch_409s_when_task_already_attached_to_another_batch(db, test_user):
    message = await _make_message(db, test_user.id)
    task = await linkedin_send_service.enqueue_send_task(
        db,
        outreach_message_id=message.id,
        linkedin_profile_url=message.recipient_linkedin_url,
        action_type="direct_message",
    )
    await linkedin_send_service.create_batch(
        db,
        triggered_by=test_user.id,
        multilogin_profile_id="profile-1",
        max_sends_per_day=10,
        task_ids=[task.id],
    )
    with pytest.raises(HTTPException) as exc_info:
        await linkedin_send_service.create_batch(
            db,
            triggered_by=test_user.id,
            multilogin_profile_id="profile-1",
            max_sends_per_day=10,
            task_ids=[task.id],
        )
    assert exc_info.value.status_code == 409


async def test_start_batch_sets_running_and_enqueues_worker_job(db, test_user):
    batch = await linkedin_send_service.create_batch(
        db,
        triggered_by=test_user.id,
        multilogin_profile_id="profile-1",
        max_sends_per_day=5,
        task_ids=[],
    )
    mock_redis = MagicMock()
    with patch("app.modules.outreach.linkedin_send_service.Queue") as mock_queue_cls:
        mock_queue_instance = MagicMock()
        mock_queue_cls.return_value = mock_queue_instance
        started = await linkedin_send_service.start_batch(
            db, batch_id=batch.id, redis_conn=mock_redis
        )

    assert started.status == "running"
    assert started.started_at is not None
    mock_queue_instance.enqueue.assert_called_once_with(
        "app.workers.tasks.linkedin_send_batch.run_linkedin_send_batch_job",
        str(batch.id),
    )


async def test_start_batch_409s_when_not_pending(db, test_user):
    batch = await linkedin_send_service.create_batch(
        db,
        triggered_by=test_user.id,
        multilogin_profile_id="profile-1",
        max_sends_per_day=5,
        task_ids=[],
    )
    await linkedin_send_service.start_batch(db, batch_id=batch.id, redis_conn=MagicMock())
    with pytest.raises(HTTPException) as exc_info:
        await linkedin_send_service.start_batch(db, batch_id=batch.id, redis_conn=MagicMock())
    assert exc_info.value.status_code == 409


async def test_start_batch_404_for_missing_batch(db):
    with pytest.raises(HTTPException) as exc_info:
        await linkedin_send_service.start_batch(db, batch_id=uuid4(), redis_conn=MagicMock())
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# HTTP-level: permission gating (linkedin_tasks:operate)
# ---------------------------------------------------------------------------


def test_create_batch_endpoint_403s_without_permission(client: TestClient, regular_user):
    response = client.post(
        "/api/outreach/linkedin-send-batches",
        headers=_auth_headers(str(regular_user.id)),
        json={"multilogin_profile_id": "profile-1", "max_sends_per_day": 5},
    )
    from tests.envelope_helpers import assert_error

    assert_error(response, 403)


def test_create_batch_endpoint_without_max_sends_per_day_rejects_422(client: TestClient, superuser):
    """Explicit release-blocking test called out in the dispatch instructions:
    creating a batch without max_sends_per_day must 422."""
    response = client.post(
        "/api/outreach/linkedin-send-batches",
        headers=_auth_headers(str(superuser.id)),
        json={"multilogin_profile_id": "profile-1"},
    )
    assert response.status_code == 422


def test_create_batch_endpoint_succeeds_for_superuser(client: TestClient, superuser):
    response = client.post(
        "/api/outreach/linkedin-send-batches",
        headers=_auth_headers(str(superuser.id)),
        json={"multilogin_profile_id": "profile-1", "max_sends_per_day": 5},
    )
    from tests.envelope_helpers import assert_success

    data = assert_success(response)
    assert data["status"] == "pending"
    assert data["max_sends_per_day"] == 5


def test_start_batch_endpoint_403s_without_permission(client: TestClient, regular_user, superuser):
    """Explicit release-blocking test: starting a batch without linkedin_tasks:operate 403s."""
    create_response = client.post(
        "/api/outreach/linkedin-send-batches",
        headers=_auth_headers(str(superuser.id)),
        json={"multilogin_profile_id": "profile-1", "max_sends_per_day": 5},
    )
    from tests.envelope_helpers import assert_error, assert_success

    batch_id = assert_success(create_response)["id"]

    response = client.post(
        f"/api/outreach/linkedin-send-batches/{batch_id}/start",
        headers=_auth_headers(str(regular_user.id)),
    )
    assert_error(response, 403)


def test_list_linkedin_tasks_endpoint_403s_without_permission(client: TestClient, regular_user):
    response = client.get(
        "/api/outreach/linkedin-tasks", headers=_auth_headers(str(regular_user.id))
    )
    from tests.envelope_helpers import assert_error

    assert_error(response, 403)


# ---------------------------------------------------------------------------
# worker job: app.workers.tasks.linkedin_send_batch — max_sends_per_day
# enforcement (halt at ceiling, resume next day)
# ---------------------------------------------------------------------------


class _SessionCM:
    def __init__(self, session) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info: object) -> bool:
        return False


async def test_sends_today_for_profile_counts_only_completed_tasks_today(db, test_user):
    message = await _make_message(db, test_user.id)
    batch = LinkedInSendBatch(
        id=uuid4(), multilogin_profile_id="profile-ceiling", max_sends_per_day=3, status="running"
    )
    db.add(batch)
    await db.flush()

    completed_today = LinkedInSendTask(
        id=uuid4(),
        outreach_message_id=message.id,
        batch_id=batch.id,
        linkedin_profile_url="https://www.linkedin.com/in/a",
        action_type="direct_message",
        status="completed",
        completed_at=datetime.now(UTC),
    )
    completed_yesterday = LinkedInSendTask(
        id=uuid4(),
        outreach_message_id=message.id,
        batch_id=batch.id,
        linkedin_profile_url="https://www.linkedin.com/in/b",
        action_type="direct_message",
        status="completed",
        completed_at=datetime.now(UTC) - timedelta(days=1),
    )
    still_pending = LinkedInSendTask(
        id=uuid4(),
        outreach_message_id=message.id,
        batch_id=batch.id,
        linkedin_profile_url="https://www.linkedin.com/in/c",
        action_type="direct_message",
        status="pending",
    )
    db.add_all([completed_today, completed_yesterday, still_pending])
    await db.commit()

    count = await _sends_today_for_profile(db, "profile-ceiling")
    assert count == 1


async def test_run_linkedin_send_batch_job_halts_at_ceiling_without_completing_tasks(db, test_user):
    """The automated-click mechanism doesn't exist yet (explicit scope cut) — the
    worker job must halt cleanly rather than mark anything sent or failed."""
    message = await _make_message(db, test_user.id)
    batch = LinkedInSendBatch(
        id=uuid4(), multilogin_profile_id="profile-halt", max_sends_per_day=1, status="running"
    )
    db.add(batch)
    await db.flush()

    already_sent_today = LinkedInSendTask(
        id=uuid4(),
        outreach_message_id=message.id,
        batch_id=batch.id,
        linkedin_profile_url="https://www.linkedin.com/in/a",
        action_type="direct_message",
        status="completed",
        completed_at=datetime.now(UTC),
    )
    pending_task = LinkedInSendTask(
        id=uuid4(),
        outreach_message_id=message.id,
        batch_id=batch.id,
        linkedin_profile_url="https://www.linkedin.com/in/b",
        action_type="direct_message",
        status="pending",
    )
    db.add_all([already_sent_today, pending_task])
    await db.commit()

    with patch(
        "app.workers.tasks.linkedin_send_batch.SessionLocal",
        side_effect=lambda: _SessionCM(db),
    ):
        await _run_linkedin_send_batch_job(str(batch.id))

    await db.refresh(pending_task)
    assert pending_task.status == "pending"


async def test_run_linkedin_send_batch_job_skips_non_running_batch(db, test_user):
    message = await _make_message(db, test_user.id)
    batch = LinkedInSendBatch(
        id=uuid4(), multilogin_profile_id="profile-x", max_sends_per_day=5, status="pending"
    )
    db.add(batch)
    await db.flush()
    pending_task = LinkedInSendTask(
        id=uuid4(),
        outreach_message_id=message.id,
        batch_id=batch.id,
        linkedin_profile_url="https://www.linkedin.com/in/x",
        action_type="direct_message",
        status="pending",
    )
    db.add(pending_task)
    await db.commit()

    with patch(
        "app.workers.tasks.linkedin_send_batch.SessionLocal",
        side_effect=lambda: _SessionCM(db),
    ):
        await _run_linkedin_send_batch_job(str(batch.id))

    await db.refresh(batch)
    assert batch.status == "pending"


def test_perform_send_action_raises_not_implemented():
    """Explicit scope-cut placeholder — asserts this always raises rather than
    silently performing (or pretending to perform) an automated send."""
    from app.workers.tasks.linkedin_send_batch import _perform_send_action

    task = LinkedInSendTask(
        id=uuid4(),
        outreach_message_id=uuid4(),
        linkedin_profile_url="https://www.linkedin.com/in/x",
        action_type="direct_message",
    )
    with pytest.raises(LinkedInSendNotImplementedError):
        _perform_send_action(task)


# ---------------------------------------------------------------------------
# Design-boundary check: zero automated-click imports
# (release-blocking per the plan's Track 06 scope cut)
# ---------------------------------------------------------------------------

_MODULE_FILES = [
    Path(inspect.getfile(linkedin_send_service)),
    Path(inspect.getfile(LinkedInSendBatch)),
]
_FORBIDDEN_IMPORT_SUBSTRINGS = (
    "app.integrations.linkedin.client",
    "app.integrations.multilogin.profile_pool",
)


def test_no_forbidden_automated_click_imports_in_linkedin_send_modules():
    import re

    import app.workers.tasks.linkedin_send_batch as batch_worker_module
    from app.modules.outreach import linkedin_send_router

    files = _MODULE_FILES + [
        Path(inspect.getfile(linkedin_send_router)),
        Path(inspect.getfile(batch_worker_module)),
    ]
    for path in files:
        source = path.read_text()
        for forbidden in _FORBIDDEN_IMPORT_SUBSTRINGS:
            pattern = rf"^\s*(import|from)\s+{re.escape(forbidden)}\b"
            assert not re.search(pattern, source, re.MULTILINE), (
                f"{path.name} imports forbidden module {forbidden}"
            )
