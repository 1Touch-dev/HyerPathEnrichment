# Foundation Week 1: Document Processing Architecture

**Status**: ✅ Complete
**Date**: 2026-08-04
**Phase**: AI Candidate Platform - Foundation Week 1

## Executive Summary

Foundation Week 1 implements a complete document processing pipeline for the AI Candidate Platform, enabling CV/resume upload, parsing, semantic chunking, embedding generation, and vector similarity search. This foundation supports the future AI Job Matching & Notifications system.

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│  DOCUMENT PROCESSING PIPELINE                                    │
└─────────────────────────────────────────────────────────────────┘

User Upload (PDF/DOCX)
      ↓
[API] POST /api/documents/upload
      ↓
[Worker-Document] Parse & Store
      ↓
[Worker-Embedding] Chunk & Embed
      ↓
[pgvector] Store Embeddings
      ↓
[API] POST /api/documents/search (Semantic Search)
```

## Architecture Components

### 1. API Layer (Agent 5)

**Module**: `backend/app/modules/documents/`

**Endpoints**:
- `POST /api/documents/upload` - Upload CV/document
- `GET /api/documents/jobs/{job_id}` - Poll processing status
- `POST /api/documents/search` - Semantic similarity search
- `GET /api/documents/{id}/cv-data` - Get structured CV data
- `GET /api/documents` - List user documents

**Security**:
- Authentication required (CurrentUser dependency)
- File type validation (PDF, DOCX only)
- Size limits (10MB max)
- SHA256-based deduplication

### 2. Document Processing Worker (Agent 1)

**Docker**: `backend/docker/Dockerfile.worker-document`
**Queue**: `document_processing` (priority: 5)

**Responsibilities**:
- PDF text extraction (PyMuPDF)
- DOCX text extraction (python-docx)
- Layout preservation
- File validation and security checks
- Storage to R2/local (.asset-cache)
- Job chaining to embedding worker

**Security Features**:
- 10MB file size limit
- MIME type verification
- File hash for deduplication
- Corrupted file detection

**Database Schema**:
```sql
CREATE TABLE candidate_documents (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    document_type VARCHAR(20),  -- 'cv', 'cover_letter'
    original_filename VARCHAR(255),
    storage_path VARCHAR(512),
    file_hash VARCHAR(64),  -- SHA256
    file_size_bytes INTEGER,
    raw_text TEXT,
    extracted_data JSONB,
    processing_status VARCHAR(20),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### 3. Semantic Chunking & CV Extraction (Agent 3)

**Module**: `backend/app/utils/text_chunking.py`, `backend/app/services/cv_extractor.py`

**Chunking Strategy**:
- LangChain RecursiveCharacterTextSplitter
- Max 512 tokens per chunk
- 50-token overlap between chunks
- Paragraph-aware splitting (\n\n boundaries)
- Token counting with tiktoken

**CV Structured Extraction**:
- OpenAI GPT-4o-mini with Structured Outputs
- Extracts: contact info, skills, experience, education, preferences
- Completeness scoring (0.0-1.0)
- Missing field tracking

**CVData Model** (20+ fields):
```python
class CVData(BaseModel):
    # Contact
    full_name, email, phone, linkedin_url, github_url, portfolio_url

    # Skills
    technical_skills, soft_skills, languages

    # Experience
    total_years_experience, current_role, current_company, work_history

    # Education
    highest_degree, field_of_study

    # Preferences
    desired_roles, desired_locations, remote_preference, salary_expectation

    # Metadata
    completeness_score, missing_fields
```

### 4. Embedding Generation Worker (Agent 2)

**Docker**: `backend/docker/Dockerfile.worker-embedding`
**Queue**: `embedding_generation` (priority: 3)

**Responsibilities**:
- Generate OpenAI embeddings (text-embedding-3-small)
- Batch processing (up to 100 texts)
- Store in pgvector
- Cost tracking
- Vector similarity search

**Embedding Configuration**:
- Model: `text-embedding-3-small`
- Dimensions: 1536
- Cost: $0.02 per 1M tokens

**Retry Logic**:
- 3 retries with exponential backoff (2s, 4s, 8s)
- Handles OpenAI API failures gracefully

**Database Schema**:
```sql
CREATE TABLE document_embeddings (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES candidate_documents(id),
    chunk_index INTEGER,
    chunk_text TEXT,
    embedding vector(1536),
    token_count INTEGER,
    created_at TIMESTAMP
);

CREATE INDEX idx_embeddings_hnsw
ON document_embeddings
USING hnsw (embedding vector_cosine_ops);
```

### 5. Vector Storage & Search (Agent 4 + Agent 2)

**pgvector Extension**: v0.7.4
**Index**: HNSW for sub-linear similarity search

**Search Features**:
- Cosine similarity
- Configurable result limit
- Document-level filtering
- SQLite fallback (Python-based cosine for development)

**Why pgvector?** (See ADR 0011):
- Already using Postgres 16
- Proven at scale (Notion, Retool, Supabase)
- Free (vs $70/month for Pinecone)
- Works for <10M vectors

### 6. Cost Monitoring & Observability (Agent 2)

**Module**: `backend/app/observability/cost_tracking.py`

**Tracking**:
- Redis counters (daily/monthly/total)
- Prometheus metrics
- Per-operation cost tracking

**Metrics**:
```python
# Daily cost
GET redis:cost:embeddings:2026-08-04

# Monthly cost
GET redis:cost:embeddings:2026-08

# Prometheus
openai_cost_total{operation="embeddings"}
openai_tokens_total{operation="embeddings"}
```

## Data Flow

### Complete Pipeline

```
1. User uploads CV (PDF/DOCX)
   ↓
2. API validates file (size, type, hash)
   ↓
3. Job created in document_jobs table (status: pending)
   ↓
4. Enqueued to document_processing queue
   ↓
5. worker-document processes:
   - Extract text (PyMuPDF/python-docx)
   - Store file (R2/local)
   - Update candidate_documents table
   - Chain to embedding_generation queue
   ↓
6. worker-embedding processes:
   - Chunk text (512 tokens, 50 overlap)
   - Generate embeddings (OpenAI)
   - Store in document_embeddings table
   - Track cost
   ↓
7. Job status updated to completed
   ↓
8. User can search semantically
```

## Technology Stack

### Core Dependencies

```toml
# Document Processing
PyMuPDF = ">=1.24,<2.0"        # PDF parsing
python-docx = ">=1.1,<2.0"     # DOCX parsing
tiktoken = ">=0.7,<1.0"        # Token counting

# Embeddings & Search
openai = ">=1.40,<2.0"         # Embeddings API
pgvector = ">=0.3,<1.0"        # Vector storage
langchain-text-splitters = ">=0.3,<1.0"  # Chunking
```

### Infrastructure

- **Database**: PostgreSQL 16 + pgvector v0.7.4
- **Queue**: Redis + RQ (Redis Queue)
- **Storage**: Cloudflare R2 / Local (.asset-cache)
- **Workers**: Docker containers (2 CPU, 1-4GB RAM)

## Performance Characteristics

### Throughput

- **Document Processing**: ~10-20 documents/minute per worker
- **Embedding Generation**: ~100 chunks/minute per worker
- **Vector Search**: <100ms for 10K embeddings (HNSW index)

### Scalability

- **Horizontal**: Scale workers independently
  ```bash
  docker-compose up -d --scale worker-document=3
  docker-compose up -d --scale worker-embedding=5
  ```

- **Vector Search**: pgvector scales to 10M+ embeddings before considering dedicated vector DB

### Cost Estimates

**Per 1000 CVs (avg 2 pages each)**:
- Document storage: ~200MB
- Embeddings: ~100K tokens = $0.002
- Total monthly (10K CVs): ~$0.20 for embeddings

## Testing

### Test Coverage

| Component | Tests | Coverage |
|-----------|-------|----------|
| Document Processor | 21 | 86% |
| Chunking | 9 | 94% |
| CV Extraction | 11 | 94% |
| Embeddings | 11 | >80% |
| Vector Search | 15 | >80% |
| Cost Tracking | 12 | >80% |

### Test Fixtures

Located in `backend/tests/fixtures/`:
- `sample_cv.pdf` - Standard 2-page resume
- `sample_cv_minimal.pdf` - 70% complete (test scoring)
- `sample_cv.docx` - Word format
- `malformed.pdf` - Corrupted (test error handling)

## Deployment

### Development

```bash
# Start all services
docker-compose -f backend/docker/docker-compose.yml \
               -f backend/docker/docker-compose.foundation.yml \
               up -d

# Check worker health
docker-compose logs worker-document
docker-compose logs worker-embedding
```

### Production

Environment variables (see `.env.foundation.example`):
```bash
ENABLE_EMBEDDINGS=true
OPENAI_API_KEY=sk-proj-...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EMBEDDING_DIMENSIONS=1536
CV_EXTRACTION_MODEL=gpt-4o-mini
DOCUMENT_UPLOAD_MAX_SIZE_MB=10
R2_ENABLED=true  # false for local dev
```

## Architecture Decision Records

- **ADR 0011**: [pgvector over dedicated vector databases](adr/0011-pgvector-vs-dedicated-vector-db.md)
- **ADR 0012**: [Semantic chunking strategy](adr/0012-semantic-chunking-strategy.md)

## Future Enhancements

### Phase 2 (Planned)

1. **Real-time Job Matching**
   - Match candidate CVs against job postings
   - Semantic similarity scoring
   - Notification system

2. **CV Quality Scoring**
   - Completeness analysis
   - Improvement suggestions
   - Missing field recommendations

3. **Interview Preparation**
   - Audio transcription (Whisper API)
   - Filler word analysis
   - AI feedback generation

## Contributors

Foundation Week 1 was implemented by 5 specialized agents:

- **Agent 4**: pgvector infrastructure (Docker, migrations, ADR)
- **Agent 1**: Document processing worker (PDF/DOCX parsing, storage)
- **Agent 3**: Semantic chunking & CV extraction
- **Agent 5**: REST API endpoints
- **Agent 2**: Embedding generation & cost monitoring

**Coordinated by**: Master Orchestrator
**Timeline**: 4 days (Aug 4-7, 2026)
**Status**: ✅ All agents merged, integration tests passing
