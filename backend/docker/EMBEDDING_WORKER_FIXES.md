# Embedding Worker Fix Summary

## Issues Fixed

### Issue 1: Function Argument Mismatch ✅ FIXED
**Problem:** Document worker was passing 2 arguments (document_id, text) but embedding worker function only accepted 1 (document_id).

**Error:**
```
TypeError: run_embedding_job() takes 1 positional argument but 2 were given
```

**Root Cause:** Code was already correct in repository (passing only document_id), but Docker containers had stale code.

**Solution:** Rebuilt Docker containers with `--no-cache` to pull fresh code.

**File:** `backend/app/workers/tasks/document.py` line 119-120
- Already correct: Only passes `document_id` to embedding queue

---

### Issue 2: Async Context Manager ✅ FIXED
**Problem:** `get_db_session()` was an async generator but not decorated as an async context manager.

**Error:**
```
TypeError: 'async_generator' object does not support the asynchronous context manager protocol
```

**Root Cause:** Missing `@asynccontextmanager` decorator on `get_db_session()` function.

**Solution:** Added decorator to enable `async with get_db_session() as session:` syntax.

**Files Changed:**
- `backend/app/database/session.py`
  - Added `from contextlib import asynccontextmanager` import
  - Added `@asynccontextmanager` decorator to `get_db_session()` function

---

### Issue 3: SQLAlchemy ORM Metadata - Missing User Model ✅ FIXED
**Problem:** CandidateDocument has FK to User, but User model wasn't imported in embedding worker, causing SQLAlchemy to fail resolving foreign keys during commit.

**Error:**
```
NoReferencedTableError: Foreign key associated with column 'candidate_documents.user_id'
could not find table 'users' with which to generate a foreign key to target column 'id'
```

**Root Cause:** SQLAlchemy needs all related models imported for FK resolution to work. The embedding worker imported `CandidateDocument` but not `User`, causing incomplete ORM metadata.

**Solution:** Added import of `User` model to embedding worker.

**Files Changed:**
- `backend/app/workers/tasks/embedding.py`
  - Added `from app.auth.models import User  # noqa: F401 - Import for SQLAlchemy FK resolution`

---

## Testing

Run the complete test script:

```bash
cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker
chmod +x test-embedding-complete.sh
./test-embedding-complete.sh
```

This will:
1. Rebuild the embedding worker with all fixes
2. Upload a test document
3. Verify embeddings are generated successfully
4. Show detailed results and logs

---

## Expected Results After Fix

✅ Document upload successful
✅ Document worker processes PDF
✅ Document worker enqueues embedding job with correct signature
✅ Embedding worker receives job
✅ Embedding worker opens database session
✅ Embedding worker resolves all FK relationships
✅ Embeddings stored in database (2-4 chunks)
✅ Document status: "embedded"
✅ No errors in logs

---

## Files Modified

1. `backend/app/database/session.py`
   - Added `asynccontextmanager` import and decorator

2. `backend/app/workers/tasks/embedding.py`
   - Added `User` model import for ORM metadata

---

## Next Steps

After running the test script successfully:
1. Commit these changes to the repository
2. Push to remote
3. The embedding worker will be fully functional
