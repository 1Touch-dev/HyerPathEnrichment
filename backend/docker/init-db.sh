#!/bin/bash
# Postgres initialization script - creates observability databases
# Runs automatically on first container startup via /docker-entrypoint-initdb.d/
set -e

echo "Creating observability databases..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create GlitchTip database (error tracking)
    CREATE DATABASE glitchtip;
    GRANT ALL PRIVILEGES ON DATABASE glitchtip TO $POSTGRES_USER;

    -- Create Langfuse database (LLM observability)
    CREATE DATABASE langfuse;
    GRANT ALL PRIVILEGES ON DATABASE langfuse TO $POSTGRES_USER;
EOSQL

echo "Observability databases created successfully."
