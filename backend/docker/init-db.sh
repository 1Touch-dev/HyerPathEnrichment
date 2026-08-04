#!/bin/bash
# Postgres initialization script - creates observability databases and enables pgvector
# Runs automatically on first container startup via /docker-entrypoint-initdb.d/
set -e

echo "Enabling pgvector extension in main database..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable pgvector extension (idempotent)
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Verify installation
    SELECT extversion FROM pg_extension WHERE extname='vector';
EOSQL

echo "Creating observability databases..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create GlitchTip database (error tracking)
    CREATE DATABASE glitchtip;
    GRANT ALL PRIVILEGES ON DATABASE glitchtip TO $POSTGRES_USER;

    -- Create Langfuse database (LLM observability)
    CREATE DATABASE langfuse;
    GRANT ALL PRIVILEGES ON DATABASE langfuse TO $POSTGRES_USER;
EOSQL

echo "pgvector extension enabled and observability databases created successfully."
