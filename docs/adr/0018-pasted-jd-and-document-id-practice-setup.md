# 0018. Pasted JD and optional document_id for interview practice setup

- **Status:** Accepted
- **Date:** 2026-08-25

## Context

Module 3 Interview Prep landing (`/app/practice`) needs a setup form that can
practice against either a role bank or a job description, including candidates
who have not yet tracked a scanned posting. The original `JdPracticeRequest`
required `job_match_id` only and rejected arbitrary pasted JDs. Separately,
résumé personalization always used the latest completed `CandidateDocument`,
with no way to choose among multiple uploads.

## Decision

We chose **mutual exclusivity of `job_match_id` XOR pasted `job_description`
(plus optional `job_title` / `company`) on the same JD practice endpoint**, and
an optional **`document_id` on both `QuestionRequest` and `JdPracticeRequest`**,
over building a second paste-only endpoint or keeping match-only JD practice.

Pasted JDs still create `session_type="jd_tailored"` sessions (same daily limit
and generator) with metadata `{"source": "pasted_jd", ...}` and a null
`job_match_id` in the response. Explicit `document_id` must be owned and ready;
invalid ids raise validation errors rather than silently falling back.

## Tradeoffs

- One endpoint serves two JD sources — slightly more schema validation, fewer
  routes for the frontend to learn.
- Pasted text is not persisted as a `JobPosting`; only session metadata retains
  title/company for the practice run.
- Callers that omit `document_id` keep the previous “latest ready CV” behavior.

## Consequences

- `backend/app/modules/jd_practice/schemas.py` and `service.py` implement XOR
  validation and the paste branch.
- `backend/app/modules/questions/service.py` `_load_candidate_context` accepts
  optional `document_id`.
- Frontend Interview Prep landing can toggle role vs JD (tracked or paste) and
  show a résumé picker when multiple CVs exist.
