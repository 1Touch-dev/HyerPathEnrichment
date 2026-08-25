# Machine 2, Track 9 — Recruiter-Initiated Apply and Suggest

## Depends on

`08-recruiter-candidate-assignment.md` conceptually (a recruiter acting on behalf of a candidate
is most often that candidate's assigned recruiter, per `08`'s "my candidates" view) but **not**
structurally — this chunk's authorization does not check `RecruiterCandidateAssignment` at all,
consistent with `08`'s explicit "assignment is not an access gate" decision. Any recruiter may
apply/suggest on behalf of any candidate, same as any other recruiter action in this shared-pool
product model. Also depends on the existing `job_matching` module (`JobMatch`, `JobPosting`) and
`app.services.email_service`/`app.modules.job_matching.push` for the candidate-facing
notification this chunk sends.

## Naming correction (apply throughout this file)

There is no separate `candidates` table in this codebase — candidate-facing preference columns
live directly on `users` (see `machine-1-tenancy-core/02-schema-and-migration.md`'s final
schema). This chunk's new preference column is therefore `users.recruiter_action_mode`, not
`candidates.recruiter_action_mode`.

## Goal

Two recruiter-initiated actions performed *on behalf of* a candidate, both gated by a new
candidate-facing preference:

1. **Apply for candidate** — a recruiter submits a job application for a candidate against a
   specific `JobMatch`/`JobPosting` (or a manual job entry), without the candidate personally
   clicking "apply."
2. **Suggest role to candidate** — a recruiter sends a candidate a role they think is a good fit,
   for the candidate to review (accept/dismiss), distinct from the existing algorithmic
   `JobMatch` surfacing pipeline (`job_matching/scorer.py`) — this is a human recruiter's manual
   pick, not a new match-scoring path.

Both actions must respect `users.recruiter_action_mode`:

- `"autonomous"` (the candidate has opted in to letting recruiters act immediately on their
  behalf) — "apply for candidate" takes effect immediately (marks the underlying
  `JobMatch.application_status`/`applied_at` as if the candidate applied themselves, per the
  existing convention in `job_matching/models.py`'s `JobMatch.application_status`); "suggest
  role" still always creates a candidate-visible suggestion (there is nothing to "auto-approve"
  for a suggestion — the candidate reviewing it is the entire point of that action, independent
  of `recruiter_action_mode`; see Ambiguities resolved below for why `recruiter_action_mode` only
  gates *apply*, not *suggest*).
- `"approval_required"` (default — see Ambiguities resolved) — "apply for candidate" creates a
  `PendingRecruiterAction` row instead of touching `JobMatch` directly; the candidate must
  approve it before the underlying application status changes.

## Files to create

- `backend/app/modules/recruiter_actions/__init__.py`
- `backend/app/modules/recruiter_actions/models.py`
- `backend/app/modules/recruiter_actions/schemas.py`
- `backend/app/modules/recruiter_actions/repository.py`
- `backend/app/modules/recruiter_actions/service.py`
- `backend/app/modules/recruiter_actions/router.py`
- `backend/alembic/versions/051_recruiter_action_mode_and_pending_actions.py` (verify real next
  number with `python -m alembic heads` from `backend/` before writing `down_revision` — this is
  at least the second track in this doc set's new-chunk batch wanting a `05x` slot, alongside
  `08`'s `050_*`; do not assume both land in the order written here)

## Files to edit

- `backend/app/auth/models.py` — add `recruiter_action_mode` to `User`.

## `backend/app/auth/models.py` edit

Add, directly after the existing `# Soft delete` block's `deleted_at` column (grouped with other
candidate-facing preference-ish columns rather than the RBAC/MFA block above it, since this is a
candidate self-service preference, not an admin-assigned attribute):

```python
    # Recruiter-initiated actions (machine-2/09): "autonomous" lets a recruiter's
    # "apply for candidate" action take effect immediately; "approval_required"
    # (default) requires the candidate to approve a pending action first. Applies
    # only to "apply for candidate" — "suggest role to candidate" is always
    # presented to the candidate for review regardless of this setting, since a
    # suggestion has no "immediate effect" to gate in the first place. See
    # machine-2-parallel-tracks/09-recruiter-initiated-apply-and-suggest.md's
    # Ambiguities resolved section for why default is approval_required, not
    # autonomous.
    recruiter_action_mode: Mapped[str] = mapped_column(
        String(20), default="approval_required", nullable=False
    )
```

## `backend/app/modules/recruiter_actions/models.py`

```python
"""Recruiter-initiated apply/suggest actions on behalf of a candidate, gated by
users.recruiter_action_mode. See this module's parent directory's
09-recruiter-initiated-apply-and-suggest.md for the full autonomous-vs-
approval_required design."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc


class PendingRecruiterAction(Base):
    """A recruiter-initiated "apply for candidate" action awaiting the candidate's
    approval (only created when the candidate's recruiter_action_mode ==
    "approval_required" at the time the recruiter acted — approval_required is
    re-checked at approve-time too, see service.py, in case the candidate changed
    their preference in between)."""

    __tablename__ = "pending_recruiter_actions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recruiter_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    action_type: Mapped[str] = mapped_column(String(20), nullable=False)  # "apply"
    # Exactly one of job_match_id/manual_job_entry_id, mirroring JobMatch's own
    # ck_job_matches_exactly_one_source convention — a pending apply action always
    # references an existing JobMatch row (created by the normal matching
    # pipeline or a manual entry), it does not fabricate a new job reference.
    job_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # "pending" | "approved" | "rejected" | "cancelled"
    recruiter_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class RoleSuggestion(Base):
    """A recruiter's manual role suggestion to a candidate, for the candidate to
    review. Independent of recruiter_action_mode — always requires candidate
    review, see Goal section."""

    __tablename__ = "role_suggestions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    candidate_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recruiter_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    job_match_id: Mapped[UUID] = mapped_column(
        ForeignKey("job_matches.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recruiter_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # "pending" | "accepted" | "dismissed"
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

Both tables reference `job_matches.id` as a bare FK string, following the exact cross-module
convention `job_matching/models.py`'s own `ManualJobEntry`-adjacent FK comment already documents
(`manual_job_entry_id: Mapped[UUID | None] = mapped_column(ForeignKey("manual_job_entries.id"...`)
— no import of `job_matching.models.JobMatch` needed for the FK declaration itself; only import
it (read-only) in `service.py` where the actual row needs to be loaded/mutated.

## `backend/app/modules/recruiter_actions/schemas.py`

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ApplyForCandidateRequest(BaseModel):
    candidate_user_id: UUID
    job_match_id: UUID
    recruiter_note: str | None = Field(default=None, max_length=1000)


class SuggestRoleRequest(BaseModel):
    candidate_user_id: UUID
    job_match_id: UUID
    recruiter_note: str | None = Field(default=None, max_length=1000)


class PendingActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    candidate_user_id: UUID
    recruiter_user_id: UUID
    job_match_id: UUID
    status: str
    recruiter_note: str | None
    created_at: datetime


class RoleSuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    candidate_user_id: UUID
    recruiter_user_id: UUID
    job_match_id: UUID
    status: str
    recruiter_note: str | None
    created_at: datetime


class RecruiterActionModeUpdateRequest(BaseModel):
    recruiter_action_mode: str = Field(..., pattern="^(autonomous|approval_required)$")
```

## `backend/app/modules/recruiter_actions/service.py` — key functions

```python
async def apply_for_candidate(
    db: AsyncSession, *, recruiter: User, body: ApplyForCandidateRequest
) -> dict[str, Any]:
    """Branches on the candidate's CURRENT recruiter_action_mode (re-read at
    call-time, not cached from anywhere) — if 'autonomous', apply immediately by
    updating the JobMatch row (mirroring the existing self-apply path's own
    application_status/applied_at write, see job_matching's own apply-tracking
    convention); if 'approval_required' (default), create a PendingRecruiterAction
    row instead and notify the candidate that a recruiter wants to apply on their
    behalf (email_service.EmailService / push.send_push_notification — reuse
    existing notification plumbing, do not build a new channel)."""
    ...


async def approve_pending_action(
    db: AsyncSession, *, candidate: User, action_id: UUID
) -> PendingActionResponse:
    """Candidate-only (action.candidate_user_id must equal candidate.id, checked
    here — 403 otherwise). Re-verifies action.status == 'pending' (409 if already
    decided) before applying the same JobMatch write apply_for_candidate's
    autonomous branch would have made directly."""
    ...


async def reject_pending_action(
    db: AsyncSession, *, candidate: User, action_id: UUID
) -> PendingActionResponse: ...


async def suggest_role(
    db: AsyncSession, *, recruiter: User, body: SuggestRoleRequest
) -> RoleSuggestionResponse:
    """Always creates a RoleSuggestion row and notifies the candidate, regardless
    of recruiter_action_mode — see Goal section for why suggest is never gated by
    this preference."""
    ...


async def respond_to_suggestion(
    db: AsyncSession, *, candidate: User, suggestion_id: UUID, accept: bool
) -> RoleSuggestionResponse: ...


async def update_recruiter_action_mode(
    db: AsyncSession, *, candidate: User, mode: str
) -> None:
    """Candidate's own self-service preference update — no permission gate beyond
    authentication, same 'caller acting on their own row' convention as 08's
    list_my_candidates."""
    ...
```

Notification reuse: locate the actual existing candidate-notification call sites before writing
this (`job_matching/push.py`'s `send_push_notification` plus whatever email-template convention
`services/email_service.py`'s `EmailTemplate` enum already uses, e.g. `JOB_MATCH_DIGEST`) — add a
new `EmailTemplate` member (e.g. `RECRUITER_ACTION_PENDING`, `ROLE_SUGGESTED`) following that
enum's existing naming convention rather than repurposing an unrelated template.

## `backend/app/modules/recruiter_actions/router.py`

```
POST   /api/recruiter-actions/apply             -> apply_for_candidate   (recruiter caller)
POST   /api/recruiter-actions/suggest           -> suggest_role          (recruiter caller)
POST   /api/recruiter-actions/pending/{id}/approve -> approve_pending_action (candidate caller)
POST   /api/recruiter-actions/pending/{id}/reject  -> reject_pending_action  (candidate caller)
POST   /api/recruiter-actions/suggestions/{id}/respond -> respond_to_suggestion (candidate caller,
                                                          body: {"accept": bool})
GET    /api/recruiter-actions/pending           -> list pending actions for the authenticated
                                                    candidate (their own only)
GET    /api/recruiter-actions/suggestions       -> list suggestions for the authenticated
                                                    candidate (their own only)
PATCH  /api/users/me/recruiter-action-mode      -> update_recruiter_action_mode (candidate's
                                                    own preference; this route lives under the
                                                    existing user-profile router if one exists —
                                                    check for an existing "update my profile"
                                                    endpoint file before adding a new router
                                                    just for this one field, following RULE.md's
                                                    "reuse, no redundancy" guidance)
```

Recruiter-facing endpoints (`apply`, `suggest`) require authentication only — no
`require_permission` gate beyond being a logged-in recruiter/staff account, consistent with `08`'s
"any recruiter can act on any candidate" model (this chunk deliberately does not add a new
permission resource for "who counts as a recruiter" — that's an existing RBAC role concern,
`04-rbac-admin-platform.md`'s territory, not this chunk's).

## Ambiguities resolved

- **Default `recruiter_action_mode`: `approval_required`, not `autonomous`.** A candidate who has
  never touched this setting should not discover that a recruiter already submitted an
  application on their behalf without their knowledge — that is a meaningfully different (and
  more surprising/risky) default than the alternative. `autonomous` is opt-in only. This mirrors
  the general principle used elsewhere in this codebase of defaulting to the more conservative,
  more candidate-protective option (e.g. `outreach`'s CAN-SPAM footer, `05`'s suppression check
  defaulting to blocking rather than allowing when uncertain).
- **Why doesn't `recruiter_action_mode` gate "suggest role"?** A suggestion has no side effect
  until the candidate acts on it — "suggest" already *is* the approval-required shape by
  construction (the candidate must accept it for it to matter). Adding a second gate on top of an
  action that's already inherently candidate-reviewed would be redundant, not more protective.

### Confirmed by leadership (2026-08-24/25)

James directly confirmed the `recruiter_action_mode` toggle design above as the candidate's own
choice, in response to a decision-list question on whether recruiter-initiated applications
should be autonomous or require approval. His words: "Approval should be option to user whether
to apply autonomously or requiring approval." This confirms the `autonomous`/`approval_required`
toggle already specified in this chunk — no design change results; the default remains
`approval_required` per this file's own "Ambiguities resolved" reasoning above, since James's
answer confirms the toggle should exist and be the candidate's choice, not which value it should
default to.
- **Does approving a pending "apply" action retroactively require the candidate's CV to be
  complete/processed?** Yes — `approve_pending_action` should perform the same "processed CV
  required" check `OutreachService.request_draft` already performs
  (`document.processing_status != "completed"` -> 409), applied to the candidate's own document,
  not the recruiter's, since the candidate is the one whose application this ultimately is.
- **Can a recruiter cancel their own pending action before the candidate responds?** Yes — add a
  `status = "cancelled"` transition reachable only by the original `recruiter_user_id` (not
  exposed as a separate endpoint above for brevity, but implement it as a natural extension of
  `apply_for_candidate`'s pending-row lifecycle if time allows; not release-blocking for this
  chunk if deferred, since a recruiter can equivalently just tell the candidate to reject it).

## Do not touch

- `backend/app/modules/job_matching/service.py`, `scorer.py`, `explainer.py` — the existing
  algorithmic match pipeline is untouched; "suggest role" is a distinct, manually-curated
  action, not a new input into match scoring.
- `backend/app/modules/outreach/` — entirely unrelated; this chunk does not touch outreach
  drafting/sending in any way, even though both features involve "recruiter acts on a
  candidate's behalf" framing.
- Do not add any new column to `JobMatch` beyond what already exists
  (`application_status`/`applied_at`/`apply_clicked_at`) — the autonomous-apply write path reuses
  those existing columns exactly as a candidate's own self-apply would set them, it does not add
  a parallel "applied_by_recruiter" flag (if a later chunk wants to distinguish recruiter-applied
  from self-applied for reporting, that's a new column decision for that chunk, not implied here).

## Verification

- Test: `apply_for_candidate` with `recruiter_action_mode="autonomous"` immediately updates the
  target `JobMatch.application_status`/`applied_at`, no `PendingRecruiterAction` row created.
- Test: `apply_for_candidate` with `recruiter_action_mode="approval_required"` (including the
  unset/default case) creates a `PendingRecruiterAction` row with `status="pending"` and does
  **not** touch `JobMatch.application_status`.
- Test: `approve_pending_action` by a user who is not `action.candidate_user_id` 403s.
- Test: `approve_pending_action` on an already-`"approved"`/`"rejected"` action 409s.
- Test: `suggest_role` always creates a `RoleSuggestion` regardless of the candidate's
  `recruiter_action_mode` value (test both values, assert identical suggestion-creation
  behavior).
- Test: candidate-facing list endpoints (`/pending`, `/suggestions`) never return another
  candidate's rows.
- Test: `update_recruiter_action_mode` rejects a value outside `{"autonomous",
  "approval_required"}` (422, via the schema's `pattern` constraint).
