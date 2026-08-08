# 0012. Semantic Chunking Strategy for Document Processing

- **Status:** Accepted
- **Date:** 2026-08-04

## Context

Foundation Week 1 introduces candidate CV processing for enrichment. CVs are long documents (1000-5000 tokens) that need to be:

1. **Chunked** for embedding generation (models have 512-8192 token limits)
2. **Semantically coherent** (avoid splitting mid-sentence or mid-paragraph)
3. **Token-aware** (accurate counting for OpenAI/embedding model limits)
4. **Overlapping** (preserve context across chunk boundaries)

Alternatives considered:

- **Fixed-size chunking**: Simple `text[0:2048]`, `text[2048:4096]`, etc. Splits mid-sentence, loses context.
- **Sentence-based chunking**: Split by periods. Doesn't respect token limits; long sentences exceed chunk size.
- **Paragraph-based chunking**: Split by `\n\n`. Better but doesn't handle token limits or overlap.

## Decision

We chose **LangChain RecursiveCharacterTextSplitter** with **tiktoken** token counting over fixed-size or sentence-based chunking because:

1. **Semantic boundaries**: Respects paragraph (`\n\n`), sentence (`. `), and word boundaries via recursive separators
2. **Token-aware**: Uses tiktoken `cl100k_base` encoding (OpenAI GPT-3.5/4 tokenizer) for accurate counting
3. **Overlap**: Configurable overlap (50 tokens) preserves context across chunks
4. **Battle-tested**: LangChain is widely used for document processing pipelines

Configuration:

- **Max tokens per chunk**: 512 (fits OpenAI embedding models like `text-embedding-3-small`)
- **Overlap**: 50 tokens (10% of chunk size)
- **Separators**: `["\n\n", "\n", ". ", " ", ""]` (paragraph → sentence → word → char)
- **Encoding**: `cl100k_base` (OpenAI standard)

## Tradeoffs

**Pros:**

- Semantic coherence (no mid-sentence splits)
- Accurate token counting (matches OpenAI models)
- Reusable for any document type (not CV-specific)
- Overlap preserves context for semantic search

**Cons:**

- Dependency on LangChain (adds 1 library)
- Slight overhead vs fixed-size chunking (~10ms/doc)
- Overlap increases storage (10% more chunks)

## Consequences

**Implementation:**

- `backend/app/utils/text_chunking.py` - Chunking logic with tiktoken
- `backend/app/services/cv_extractor.py` - Uses chunks for extraction (future: embeddings)
- `backend/tests/test_chunking.py` - Tests for token limits, overlap, boundaries

**Next steps:**

- Agent 2 will use these chunks for embedding generation
- Chunks stored with `chunk_index`, `start_char`, `end_char` for provenance
- Future: Use chunks for semantic search in candidate database

**Future work:**

- Consider adaptive chunk sizes (smaller for dense sections, larger for sparse)
- Add metadata extraction per chunk (e.g., section headers)
