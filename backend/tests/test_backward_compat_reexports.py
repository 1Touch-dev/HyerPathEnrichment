"""Tests for tiny backward-compatible re-export shims and standalone metric modules.

These modules are trivial (module-level imports/assignments), but nothing in the
existing test suite imports them directly, so they were showing up as fully
uncovered. Importing them and touching their public surface is enough to
exercise every statement.
"""

from __future__ import annotations


def test_storage_db_shim_reexports_session_module() -> None:
    from app.database.session import SessionLocal, engine, get_db_session, init_db
    from app.storage import db

    assert db.SessionLocal is SessionLocal
    assert db.engine is engine
    assert db.get_db_session is get_db_session
    assert db.init_db is init_db
    assert set(db.__all__) == {
        "SessionLocal",
        "alembic_config",
        "engine",
        "get_db_session",
        "init_db",
        "run_migrations",
    }


def test_workers_jobs_shim_reexports_run_enrichment_job() -> None:
    from app.workers import jobs
    from app.workers.tasks.enrichment import run_enrichment_job

    assert jobs.run_enrichment_job is run_enrichment_job
    assert jobs.__all__ == ["run_enrichment_job"]


def test_domain_jobs_reexports_job_status() -> None:
    from app.domain import jobs
    from app.domain.enums import JobStatus

    assert jobs.JobStatus is JobStatus
    assert jobs.__all__ == ["JobStatus"]


def test_session_metrics_module_defines_expected_collectors() -> None:
    from app.observability import session_metrics

    assert session_metrics.sessions_created_total is not None
    assert session_metrics.sessions_completed_total is not None
    assert session_metrics.session_duration_seconds is not None
    assert session_metrics.attempts_created_total is not None
    assert session_metrics.attempt_score_distribution is not None
    assert session_metrics.active_sessions is not None
    assert session_metrics.state_transitions_total is not None
