"""
Backward-compatible shim.

Some tests/docs historically referenced `app.storage.db` as the DB/Alembic entrypoint.
The canonical implementation lives in `app.database.session`.
"""

from app.database.session import (  # re-export for backward compatibility
    SessionLocal,
    alembic_config,
    engine,
    get_db_session,
    init_db,
    run_migrations,
)

__all__ = [
    "SessionLocal",
    "alembic_config",
    "engine",
    "get_db_session",
    "init_db",
    "run_migrations",
]

