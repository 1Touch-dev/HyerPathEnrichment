"""Compatibility shim — prefer ``app.database.session``."""

from app.database.session import (  # noqa: F401
    BASELINE_REVISION,
    SessionLocal,
    alembic_config,
    engine,
    get_db_session,
    init_db,
    legacy_pre_alembic,
    run_migrations,
)

__all__ = [
    "BASELINE_REVISION",
    "SessionLocal",
    "alembic_config",
    "engine",
    "get_db_session",
    "init_db",
    "legacy_pre_alembic",
    "run_migrations",
]
