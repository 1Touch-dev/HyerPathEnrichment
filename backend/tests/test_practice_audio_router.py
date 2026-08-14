"""API tests for POST /api/practice/audio and GET /api/practice/audio/{id}.

Covers: auth enforcement, the transcribe+analyze happy path (with Whisper and
storage I/O mocked), the oversized-file rejection, and cross-user 404 scoping
on the status lookup - matching the "status code, auth, response shape"
convention used by ``test_module2_api.py`` and ``test_questions_router.py``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.clients.speech import TranscriptionResult
from app.core.config import get_settings
from app.main import app
from app.modules.sessions.models import PracticeAudioRecording, PracticeSession
from tests.envelope_helpers import assert_error, assert_success


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


def _auth_headers(user_id: str | None = None) -> dict[str, str]:
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.api_token}",
        "X-Test-User-ID": user_id or str(uuid4()),
    }


@pytest.fixture
async def practice_session_fixture(db: AsyncSession) -> dict[str, Any]:
    """Seed a real user + PracticeSession, matching test_session_tracking.py's
    construction pattern for PracticeSession (id, user_id, session_type,
    status, started_at, session_metadata)."""
    user_id = uuid4()
    user = User(
        id=user_id,
        email=f"api-audio-{user_id.hex[:8]}@example.com",
        first_name="Api",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)

    session = PracticeSession(
        id=uuid4(),
        user_id=user_id,
        session_type="behavioral",
        status="in_progress",
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return {"user_id": user_id, "session": session}


@pytest.fixture
async def other_users_recording(db: AsyncSession) -> dict[str, Any]:
    """Seed a PracticeAudioRecording owned by one user, plus a separate
    requesting user's id, for the cross-user 404-scoping test."""
    owner_id = uuid4()
    owner = User(
        id=owner_id,
        email=f"api-audio-owner-{owner_id.hex[:8]}@example.com",
        first_name="Owner",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(owner)

    session = PracticeSession(
        id=uuid4(),
        user_id=owner_id,
        session_type="behavioral",
        status="in_progress",
    )
    db.add(session)
    await db.flush()

    recording = PracticeAudioRecording(
        id=uuid4(),
        user_id=owner_id,
        practice_session_id=session.id,
        storage_path="practice-audio/owner/session/rec.webm",
        file_size_bytes=2048,
        audio_format="audio/webm",
        transcription_status="completed",
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)

    other_user_id = uuid4()
    return {"owner_id": owner_id, "recording": recording, "other_user_id": other_user_id}


def test_upload_audio_requires_auth(client: TestClient) -> None:
    """No auth headers -> 401.

    Router-level ``dependencies=[Depends(current_verified_user)]`` (see
    app/main.py) plus the endpoint's own ``user: VerifiedUser`` parameter are
    both resolved as sub-dependencies by FastAPI *before* form/file body
    params are parsed, so an empty POST body is sufficient to prove auth is
    checked first (confirmed empirically below - no 422 was observed).
    """
    response = client.post("/api/practice/audio")
    assert_error(response, 401)


def test_upload_audio_transcribes_and_analyzes(
    client: TestClient, practice_session_fixture: dict[str, Any]
) -> None:
    session = practice_session_fixture["session"]
    headers = _auth_headers(str(practice_session_fixture["user_id"]))

    with (
        patch(
            "app.clients.speech.WhisperClient.transcribe_audio", new_callable=AsyncMock
        ) as mock_transcribe,
        patch(
            "app.services.audio_storage.AudioStorageClient.upload_audio", new_callable=AsyncMock
        ) as mock_upload,
    ):
        mock_transcribe.return_value = TranscriptionResult(
            text="This is my answer, um, yeah.", duration=12.5
        )
        mock_upload.return_value = ("practice-audio/mock-user/mock-session/mock123.webm", 17)

        response = client.post(
            "/api/practice/audio",
            headers=headers,
            data={"practice_session_id": str(session.id), "audio_format": "audio/webm"},
            files={"file": ("recording.webm", b"fake-audio-bytes", "audio/webm")},
        )

        mock_transcribe.assert_called_once()
        mock_upload.assert_called_once()

    data = assert_success(response)
    assert data["transcription_status"] == "completed"


def test_upload_audio_rejects_oversized_file(
    client: TestClient, practice_session_fixture: dict[str, Any]
) -> None:
    """service.upload_and_process_audio compares len(audio_bytes) against
    settings.practice_audio_max_upload_mb (default 25MB, app/core/config.py)
    and raises ValidationAppError -> 400 (app/core/errors.py), before any
    storage or transcription call is made - so nothing else needs mocking.
    """
    session = practice_session_fixture["session"]
    headers = _auth_headers(str(practice_session_fixture["user_id"]))

    settings = get_settings()
    oversized = b"x" * ((settings.practice_audio_max_upload_mb + 1) * 1024 * 1024)

    response = client.post(
        "/api/practice/audio",
        headers=headers,
        data={"practice_session_id": str(session.id), "audio_format": "audio/webm"},
        files={"file": ("big.webm", oversized, "audio/webm")},
    )
    assert_error(response, 400)


def test_get_audio_status_not_found_for_other_user(
    client: TestClient, other_users_recording: dict[str, Any]
) -> None:
    """router.get_audio_status scopes the lookup by
    (PracticeAudioRecording.id == recording_id) AND (.user_id == user.id) and
    raises NotFoundError (404) rather than a 403 when the row belongs to a
    different user - confirmed by reading router.py's GET handler.
    """
    recording = other_users_recording["recording"]
    headers = _auth_headers(str(other_users_recording["other_user_id"]))

    response = client.get(f"/api/practice/audio/{recording.id}", headers=headers)
    assert_error(response, 404)
