# 0011. pgvector over dedicated vector databases

- **Status:** Accepted
- **Date:** 2026-08-04

## Context

AI Candidate Platform (Foundation Week 1) needs to store vector embeddings for candidate profiles to enable semantic search and similarity matching. Options considered:

1. **pgvector** (Postgres extension)
2. **Pinecone** (managed vector DB)
3. **Weaviate** (self-hosted vector DB)
4. **Milvus** (open-source vector DB)
5. **Qdrant** (vector search engine)

Key requirements:
- Store 1536-dimensional OpenAI embeddings
- Support HNSW indexing for fast similarity search
- Minimal operational overhead
- Cost-effective for early-stage product
- Consistent with existing Postgres infrastructure

## Decision

We chose **pgvector extension in our existing Postgres database** over **dedicated vector databases** (Pinecone, Weaviate, Milvus, Qdrant) because:

### Technical fit
- **Already using Postgres**: We have Postgres 16 for relational data (jobs, users, audit). Adding pgvector consolidates infrastructure instead of introducing a second database.
- **Proven at scale**: Companies like Notion, Retool, and Supabase use pgvector in production for millions of embeddings.
- **HNSW indexing**: pgvector 0.7.4 supports HNSW (Hierarchical Navigable Small World) indexes for sub-linear similarity search, matching dedicated vector DBs.
- **Standard SQL**: Embeddings live alongside candidate data; no cross-database joins or dual-write patterns.

### Operational simplicity
- **Zero new services**: No separate vector DB to deploy, monitor, backup, or upgrade.
- **Existing backup strategy**: pgvector columns are backed up with `pg_dump` — no separate vector backup pipeline.
- **Same connection pool**: Reuse existing `asyncpg` pool; no new client library.

### Cost
- **Free**: pgvector is open-source (PostgreSQL license). Pinecone charges per vector (starts at $70/month for 1M 1536-dim vectors).
- **No vendor lock-in**: Can migrate to dedicated vector DB later if scale demands it, but early evidence suggests pgvector scales to 10M+ vectors before performance degrades.

### Evidence
- **Notion**: [Engineering blog post](https://www.notion.so/blog/how-we-built-notion-ai) — uses pgvector for semantic search across 10M+ pages.
- **Retool**: [Blog post](https://retool.com/blog/embeddings-in-postgres-with-pgvector/) — pgvector for internal tool search.
- **Supabase**: Offers pgvector as default vector storage; benchmarks show [comparable performance to Pinecone for <1M vectors](https://supabase.com/blog/pgvector-vs-pinecone).

### When to reconsider
Dedicated vector DBs make sense when:
- **>10M embeddings**: pgvector HNSW performance degrades beyond this scale.
- **Real-time updates**: High-frequency embedding updates (>10K/sec) benefit from vector-optimized write paths.
- **Multi-modal embeddings**: Need image/audio embeddings with specialized indexing (pgvector only supports float32 vectors).

For Foundation Week 1 (~1K candidates), pgvector is the clear winner.

## Tradeoffs

- **Limited vector operations**: pgvector supports cosine/L2/inner product distance only. No approximate nearest neighbor filters (e.g., "find similar vectors where age > 30"). Workaround: filter in SQL `WHERE` clause before vector search.
- **Postgres scalability**: Adding vector columns increases Postgres storage/memory footprint. At 1536 dims × 4 bytes = 6KB per embedding, 1M candidates = 6GB. Manageable for Postgres, but dedicated vector DBs optimize for this.
- **Migration effort if outgrown**: Moving to Pinecone/Weaviate later requires data migration + application rewrites. However, pgvector's SQL interface makes this straightforward (`COPY TO` + vendor bulk import).

## Consequences

### Implementation
1. **Dockerfile.postgres**: Install pgvector v0.7.4 from source.
2. **init-db.sh**: Enable `CREATE EXTENSION vector` in main database.
3. **Alembic migration 009**: Idempotent `CREATE EXTENSION IF NOT EXISTS vector`.
4. **SQLite compatibility**: SQLite has no vector extension; migrations pass through (vector columns unused in local dev).

### Usage
```sql
-- Create table with vector column
CREATE TABLE candidates (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  embedding vector(1536)  -- OpenAI ada-002 embeddings
);

-- Create HNSW index for fast similarity search
CREATE INDEX ON candidates USING hnsw (embedding vector_cosine_ops);

-- Find similar candidates (cosine similarity)
SELECT id, name, 1 - (embedding <=> '[0.1, 0.2, ...]'::vector) AS similarity
FROM candidates
ORDER BY embedding <=> '[0.1, 0.2, ...]'::vector
LIMIT 10;
```

### Testing
See Agent 4 deliverables (PR #TBD) for Docker build + verification tests.

### Related ADRs
- [0002-sqlite-local-postgres-docker](0002-sqlite-local-postgres-docker.md): Why we use Postgres in Docker/prod.

### References
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Notion AI blog post](https://www.notion.so/blog/how-we-built-notion-ai)
- [Retool embeddings post](https://retool.com/blog/embeddings-in-postgres-with-pgvector/)
- [Supabase pgvector benchmarks](https://supabase.com/blog/pgvector-vs-pinecone)
