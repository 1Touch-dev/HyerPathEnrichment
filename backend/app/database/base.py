from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase

# Postgres: jsonb; SQLite (local/tests): json. Single ORM type for both dialects.
JsonDoc = JSONB().with_variant(JSON(), "sqlite")


class Base(DeclarativeBase):
    pass
