"""Regression test for phase2_module3.md §4.3: practice_audio_recordings had
a real table (migration 017) but no ORM model. This test asserts the ORM
class now round-trips correctly against the same table audio_cleanup.py
already reads via raw SQL - both code paths must agree on the schema.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.modules.sessions.models import PracticeAudioRecording, PracticeSession


async def test_orm_model_round_trips_against_migration_017_table(db: AsyncSession) -> None:
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email=f"model-audio-{user_id.hex[:8]}@example.com",
        first_name="Model",
        last_name="User",
        is_active=True,
        is_verified=True,
    )
    db.add(user)

    session = PracticeSession(
        id=uuid.uuid4(),
        user_id=user_id,
        session_type="behavioral",
        status="in_progress",
    )
    db.add(session)
    await db.flush()

    recording = PracticeAudioRecording(
        id=uuid.uuid4(),
        user_id=user_id,
        practice_session_id=session.id,
        storage_path="audio/test.webm",
        file_size_bytes=1024,
        audio_format="audio/webm",
        transcription_status="pending",
    )
    db.add(recording)
    await db.commit()

    # On SQLite, PGUUID(as_uuid=True)'s bind_processor stores UUIDs as 32-char
    # hex (no dashes) - the same format audio_cleanup.py's raw SQL reads back
    # natively, so the WHERE clause must bind that format too, not str(uuid)
    # (which includes dashes and would silently match zero rows).
    raw_row = (
        await db.execute(
            text("SELECT storage_path FROM practice_audio_recordings WHERE id = :id"),
            {"id": recording.id.hex},
        )
    ).fetchone()
    assert raw_row is not None
    assert raw_row.storage_path == "audio/test.webm"
