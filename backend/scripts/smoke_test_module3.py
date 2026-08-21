#!/usr/bin/env python3
"""Real end-to-end HTTP smoke test for Module 3 (Interview Prep & Sentiment Analysis).

Unlike the pytest suite (TestClient + dependency overrides), this script talks to a
REAL running uvicorn process over real HTTP, with a REAL Redis-backed RQ worker
processing background jobs, and REAL cookie-based auth (register -> verify -> login),
exactly as a real client would. See backend/docs/MODULE3_REALWORLD_TESTING.md for how
to point this at real OpenAI/Hume keys instead of the free/fail-soft path used here.

Usage:
    BASE_URL=http://127.0.0.1:8010 SMOKE_DB_PATH=/tmp/smoke.db \
        .venv/bin/python scripts/smoke_test_module3.py
"""

from __future__ import annotations

import io
import os
import sqlite3
import sys
import time
import uuid
import wave

import httpx

BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8010")
DB_PATH = os.environ.get("SMOKE_DB_PATH", "/tmp/smoke.db")
WORKER_LOG_PATH = os.environ.get("SMOKE_WORKER_LOG", "/tmp/smoke-worker.log")
TIMEOUT = 20.0

results: list[tuple[str, bool, str]] = []


def record(step: str, ok: bool, detail: str = "") -> None:
    results.append((step, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"{status}  {step}" + (f"  ({detail})" if detail else ""))
    if not ok:
        print(f"\nSmoke test aborted at: {step}")
        print_summary()
        sys.exit(1)


def print_summary() -> None:
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} steps passed")


def make_silent_wav(seconds: float = 1.0, framerate: int = 16000) -> bytes:
    """Generate a tiny valid (silent) WAV file - real audio bytes, no external deps."""
    n_frames = int(seconds * framerate)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(framerate)
        wf.writeframes(b"\x00\x00" * n_frames)
    return buf.getvalue()


def get_verification_token(email: str) -> str:
    """Read the verification token directly from the DB.

    EMAIL_TEST_MODE=true means no real email is sent (see
    app/services/email_service.py), so a real client would click a link in their
    inbox; this script reads the same token the (unsent) email would have
    contained, straight from email_verification_tokens.
    """
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(
            "SELECT t.token FROM email_verification_tokens t "
            "JOIN users u ON u.id = t.user_id WHERE u.email = ? "
            "ORDER BY t.created_at DESC LIMIT 1",
            (email,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise RuntimeError(f"No verification token found for {email}")
    return str(row[0])


def main() -> None:
    client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    # 1. Health check
    resp = client.get("/health")
    record("GET /health", resp.status_code == 200 and resp.json()["data"]["status"] == "ok")

    # 2. Register
    email = f"smoketest-{uuid.uuid4().hex[:10]}@example.com"
    password = "SmokeTest!12345"
    resp = client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "first_name": "Smoke",
            "last_name": "Test",
        },
    )
    record("POST /auth/register", resp.status_code == 201, f"status={resp.status_code}")

    # 3. Read verification token directly from DB (simulates clicking the email link)
    token = get_verification_token(email)
    record("Read verification token from DB", bool(token))

    # 4. Verify email
    resp = client.post("/auth/verify-email", json={"token": token})
    record("POST /auth/verify-email", resp.status_code == 200, f"status={resp.status_code}")

    # 5. Login (sets HttpOnly cookie on the client's cookie jar)
    resp = client.post("/auth/login", json={"email": email, "password": password})
    record("POST /auth/login", resp.status_code == 200, f"status={resp.status_code}")

    # 6. Confirm authenticated + verified
    resp = client.get("/auth/me")
    is_verified = resp.status_code == 200 and resp.json()["is_verified"] is True
    record("GET /auth/me (is_verified=true)", is_verified, f"status={resp.status_code}")

    # 7. Create a practice session
    resp = client.post("/sessions", json={"session_type": "mock_interview"})
    record("POST /sessions", resp.status_code == 201, f"status={resp.status_code}")
    session_id = resp.json()["data"]["id"]

    # 8. Fetch interview questions (question-bank path; no OPENAI_API_KEY -> falls
    #    back gracefully per Decision in ADR 0017 / .env.example's "Direct OpenAI
    #    usage" note, rather than crashing).
    resp = client.post(
        "/api/questions",
        json={"job_role": "software_engineer", "count": 3, "personalize": False},
    )
    record("POST /api/questions", resp.status_code == 200, f"status={resp.status_code}")
    questions = resp.json()["data"]["questions"]
    record(
        "questions non-empty (question bank seeded)", len(questions) > 0, f"count={len(questions)}"
    )
    question_id = questions[0]["id"] if questions else None

    # 9. Submit a text attempt -> enqueues a real RQ 'feedback' job
    resp = client.post(
        f"/sessions/{session_id}/attempts",
        json={
            "question_id": question_id,
            "response_type": "text",
            "text_response": "I would first clarify requirements, then break the problem into "
            "smaller pieces, validate my approach with a teammate, and iterate.",
        },
    )
    record(
        "POST /sessions/{id}/attempts (text)", resp.status_code == 201, f"status={resp.status_code}"
    )
    attempt_id = resp.json()["data"]["id"]
    record(
        "attempt aiScore starts null (feedback job queued, not yet processed)",
        resp.json()["data"]["ai_score"] is None,
    )

    # 10. Poll until the real RQ worker has processed the feedback job (no
    #     OPENAI_API_KEY set for this free/fail-soft run -> the worker should log a
    #     handled failure and move on, per app/workers/tasks/feedback.py, rather than
    #     leaving the job stuck or crashing the process). QuestionAttemptResponse
    #     doesn't expose attempt_metadata, so "worker consumed the job" is confirmed
    #     via the worker's own log output for this attempt id.
    deadline = time.time() + 20
    worker_consumed_job = False
    final_ai_score = None
    while time.time() < deadline:
        resp = client.get(f"/sessions/{session_id}")
        attempts = resp.json()["data"]["attempts"]
        match = next((a for a in attempts if a["id"] == attempt_id), None)
        if match and match["ai_score"] is not None:
            final_ai_score = match["ai_score"]
            worker_consumed_job = True
            break
        if os.path.exists(WORKER_LOG_PATH):
            with open(WORKER_LOG_PATH) as f:
                log_text = f.read()
            if attempt_id in log_text and (
                f"Feedback generation failed for attempt {attempt_id}" in log_text
                or f"Feedback generated successfully for attempt {attempt_id}" in log_text
            ):
                worker_consumed_job = True
                break
        time.sleep(1)
    record(
        "RQ worker consumed the feedback job (scored, or failed soft with no key)",
        worker_consumed_job,
        f"ai_score={final_ai_score}" if worker_consumed_job else "TIMEOUT waiting for worker",
    )

    # 11. Upload a real (silent) WAV file -> real transcription attempt
    wav_bytes = make_silent_wav()
    resp = client.post(
        "/api/practice/audio",
        data={"practice_session_id": session_id, "audio_format": "audio/wav"},
        files={"file": ("smoke-test.wav", wav_bytes, "audio/wav")},
    )
    record("POST /api/practice/audio", resp.status_code == 200, f"status={resp.status_code}")
    recording_id = resp.json()["data"]["id"]

    # 12. Poll the recording until the transcription pipeline reaches a terminal
    #     state (no OPENAI_API_KEY -> WhisperError -> transcription_status="failed",
    #     per app/modules/practice_audio/service.py - a legitimate terminal state,
    #     not a bug, for this free/fail-soft smoke-test run).
    deadline = time.time() + 20
    terminal_status = None
    while time.time() < deadline:
        resp = client.get(f"/api/practice/audio/{recording_id}")
        status_value = resp.json()["data"]["transcription_status"]
        if status_value in {"completed", "failed"}:
            terminal_status = status_value
            break
        time.sleep(1)
    record(
        "audio recording reaches a terminal transcription_status",
        terminal_status is not None,
        f"status={terminal_status}",
    )

    print_summary()
    print("\nAll smoke test steps completed.")


if __name__ == "__main__":
    main()
