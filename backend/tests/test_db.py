from sqlalchemy.ext.asyncio import create_async_engine


async def test_db_postgres_url_parses() -> None:
    """asyncpg dialect must be importable and the Docker URL must parse.

    No connection is made — this guards against a missing asyncpg dependency
    breaking the Postgres wiring used in docker-compose.
    """
    engine = create_async_engine("postgresql+asyncpg://hyrepath:hyrepath@postgres:5432/hyrepath")
    assert engine.dialect.name == "postgresql"
    assert engine.dialect.driver == "asyncpg"
    await engine.dispose()
