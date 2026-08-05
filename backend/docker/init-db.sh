#!/bin/bash
set -e

# Initialize PostgreSQL database with pgvector extension
# This script runs automatically on first database initialization

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Enable pgvector extension for vector embeddings
    CREATE EXTENSION IF NOT EXISTS vector;

    -- Verify extension is installed
    SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';
EOSQL

echo "✅ pgvector extension initialized successfully"
