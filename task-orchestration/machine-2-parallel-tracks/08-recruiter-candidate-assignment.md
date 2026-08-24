# Machine 2, Track 8 — Recruiter–Candidate Assignment

## Depends on

`machine-1-tenancy-core/02-schema-and-migration.md`'s `Brand` model and its removal of
`users.org_id` as an access-control column — this chunk's whole design (assignment as an
ownership marker, not a scoping gate) only makes sense once there is a single shared
candidate/recruiter pool with no org-level data isolation. If `02` has not landed yet, this
chunk's migration should still target whatever the real current Alembic head is — it does not
otherwise depend on `02`'s specific columns, only on the product model `02` establishes.

## Goal — ownership marker, explicitly NOT an access-control gate

Recruiters need a way to know "which candidates are mine" for workload visibility and
notification routing. This chunk adds `recruiter_candidate_assignments`, a plain many-to-many
join table between recruiters and candidates (both `User` rows).

**This table must never be used to filter, restrict, or gate which candidates a recruiter can
search, view, or act on.** Any recruiter can still query the full shared candidate pool, open
any candidate's profile, draft outreach for any candidate, and take any other recruiter action
regardless of whether an assignment row exists. Assignment only drives three read-side
conveniences:

1. A "my assigned candidates" view/filter (`GET .../my-candidates`) — a UI convenience, not a
   security boundary.
2. Workload reporting (e.g. "recruiter X has 40 assigned candidates" in an admin dashboard) —
   out of scope for this chunk's own files (a future admin-analytics chunk can query this table
   directly; it needs no new column or index beyond what's specified below to support a simple
   `GROUP BY recruiter_user_id` count).
3. Notification routing — when something changes on a candidate (e.g. a new job match, a status
   update), a recruiter *assigned* to that candidate is a natural target for a "your candidate
   had activity" notification, in addition to whatever candidate-facing notification already
   fires. This chunk defines the read path (`list_assigned_recruiters_for_candidate`) that a
   later notification-dispatch chunk can call; it does not itself send any notification.

Do not add a `WHERE recruiter_id = current_user.id` (or equivalent) filter to any *other*
module's existing candidate-listing query as part of this chunk — that would silently turn this
into the access-restrictive design explicitly rejected below. If a reviewer of a later chunk
sees such a filter added citing this table, it is out of scope and should be rejected.

## Files to create

- `backend/app/modules/recruiter_assignment/__init__.py`
- `backend/app/modules/recruiter_assignment/models.py`
- `backend/app/modules/recruiter_assignment/schemas.py`
- `backend/app/modules/recruiter_assignment/repository.py`
- `backend/app/modules/recruiter_assignment/service.py`
- `backend/app/modules/recruiter_assignment/router.py`
- `backend/alembic/versions/050_recruiter_candidate_assignments.py` (verify the real current head
  with `python -m alembic heads` from `backend/` before writing `down_revision` — several tracks
  in this doc set have historically raced for the same migration number; do not assume `050` is
  actually free)

## `backend/app/modules/recruiter_assignment/models.py`

```python
"""Recruiter-candidate assignment: an ownership/responsibility marker on a single
shared candidate pool, NOT an access-control boundary. See this module's parent
directory's 08-recruiter-candidate-assignment.md Goal section for the full
rationale — any recruiter can still search/view/act on any candidate regardless
of whether a row exists here."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RecruiterCandidateAssignment(Base):
    """Many-to-many: one recruiter <-> one candidate, both rows in `users`.
    A candidate may have zero, one, or several assigned recruiters (co-ownership,
    e.g. handoff during a recruiter's leave, is allowed by design — this chunk
    does not enforce "at most one recruiter per candidate")."""

    __tablename__ = "recruiter_candidate_assignments"
    __table_args__ = (
        UniqueConstraint(
            "recruiter_user_id", "candidate_user_id", name="uq_recruiter_candidate_assignment"
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recruiter_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

`assigned_by` is nullable (not the same user as `recruiter_user_id` in the common case — an
admin/team lead assigns a candidate to a recruiter, so `assigned_by` records who made the call,
not who was assigned). `NULL` covers system/migration-seeded assignments with no human actor.

Both FKs point at `users.id` as a bare string reference (no `relationship()` import needed for
this chunk's own read paths below), matching the existing cross-module FK convention already
used throughout this codebase (e.g. `job_matching/models.py`'s `JobMatch.user_id`,
`outreach/linkedin_send_models.py`'s `claimed_by` in `06`).

## `backend/app/modules/recruiter_assignment/schemas.py`

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AssignCandidateRequest(BaseModel):
    candidate_user_id: UUID
    recruiter_user_id: UUID


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    recruiter_user_id: UUID
    candidate_user_id: UUID
    assigned_by: UUID | None
    assigned_at: datetime


class MyCandidatesListResponse(BaseModel):
    assignments: list[AssignmentResponse]
```

## `backend/app/modules/recruiter_assignment/repository.py`

Plain async functions taking `db: AsyncSession`, following the existing pattern in
`backend/app/modules/orgs/repository.py`-style modules (or, if `orgs/` was never actually
created because `machine-1`'s naming pivoted straight to `brands/`, the equivalent
`backend/app/modules/brands/repository.py` — check whichever actually exists in the real tree at
implementation time and mirror its function-signature style):

```python
async def create_assignment(
    db: AsyncSession, *, recruiter_user_id: UUID, candidate_user_id: UUID, assigned_by: UUID | None
) -> RecruiterCandidateAssignment: ...

async def delete_assignment(
    db: AsyncSession, *, recruiter_user_id: UUID, candidate_user_id: UUID
) -> bool:
    """Returns False if no matching row existed (idempotent unassign)."""
    ...

async def list_assignments_for_recruiter(
    db: AsyncSession, recruiter_user_id: UUID
) -> list[RecruiterCandidateAssignment]: ...

async def list_assigned_recruiters_for_candidate(
    db: AsyncSession, candidate_user_id: UUID
) -> list[RecruiterCandidateAssignment]:
    """Read path for a future notification-dispatch chunk (see Goal §3) — not called
    by anything in this chunk itself, provided so that chunk doesn't have to add its
    own query against this table's raw columns."""
    ...
```

`create_assignment` should be idempotent-safe against the `uq_recruiter_candidate_assignment`
constraint: catch `IntegrityError` from a duplicate insert and re-fetch/return the existing row
rather than letting a 500 surface for "assign a candidate who's already assigned to this
recruiter" (a plausible double-click/retry case, not a real error).

## `backend/app/modules/recruiter_assignment/service.py`

Thin business-logic wrapper enforcing the two access-control checks that *do* apply here (who
may assign, not which candidates exist to be assigned — reiterating the Goal section's
boundary):

```python
async def assign_candidate(
    db: AsyncSession, *, actor: User, body: AssignCandidateRequest
) -> AssignmentResponse:
    """Gated by require_permission("recruiter_assignments", "write") at the router
    layer (new resource:action pair, seeded by this chunk's migration) — this
    function itself does not re-check permissions, following the existing
    convention where router-level Depends() is the enforcement point and service
    functions trust their caller (see roles_service.py's create_role, which does
    the same)."""
    ...


async def unassign_candidate(
    db: AsyncSession, *, actor: User, recruiter_user_id: UUID, candidate_user_id: UUID
) -> None: ...


async def list_my_candidates(db: AsyncSession, *, recruiter_user_id: UUID) -> MyCandidatesListResponse:
    """No permission gate beyond authentication — a recruiter listing their own
    assignments is always allowed; this is the one read path that IS scoped to
    the caller, but by caller-identity convenience, not by a security boundary
    hiding other candidates (a recruiter can still list/search all candidates via
    the existing unscoped candidate-listing endpoints elsewhere in the codebase)."""
    ...
```

## `backend/app/modules/recruiter_assignment/router.py`

```
POST   /api/recruiter-assignments               -> assign_candidate
DELETE /api/recruiter-assignments/{candidate_user_id}  -> unassign_candidate (path param
                                                          candidate_user_id; recruiter_user_id
                                                          taken from the authenticated caller,
                                                          not the request body, so a recruiter
                                                          can only unassign themselves from a
                                                          candidate, not detach a different
                                                          recruiter — an admin wanting to
                                                          reassign should call assign_candidate
                                                          for the new recruiter, not unassign on
                                                          the old one's behalf, unless the admin
                                                          is also acting with elevated
                                                          "recruiter_assignments":"write" scope,
                                                          which this endpoint's permission gate
                                                          already allows)
GET    /api/recruiter-assignments/my-candidates  -> list_my_candidates (caller-scoped, no
                                                          special permission beyond auth)
```

Gate `assign_candidate`/`unassign_candidate`-on-behalf-of-another-recruiter behind
`require_permission("recruiter_assignments", "write")` (new resource:action pair, seed via this
chunk's migration, following `04-rbac-admin-platform.md`'s seeding pattern — if `04` has not yet
landed, seed the permission row directly here rather than blocking on `04`, same "do not block"
convention `04` itself already establishes for its own agency-role seeding relative to
`machine-1`). A recruiter unassigning *themselves* from a candidate (`DELETE
/api/recruiter-assignments/{candidate_user_id}` where the path implicitly targets the caller) may
be allowed without the elevated permission — implementer's choice which of these two shapes to
expose; document whichever is chosen in the router's docstring so it's unambiguous to a later
reader which identity `recruiter_user_id` resolves from on the delete path.

## Migration: `050_recruiter_candidate_assignments.py`

```python
def upgrade() -> None:
    op.create_table(
        "recruiter_candidate_assignments",
        sa.Column("id", _uuid_type(), primary_key=True),
        sa.Column("recruiter_user_id", _uuid_type(), nullable=False),
        sa.Column("candidate_user_id", _uuid_type(), nullable=False),
        sa.Column("assigned_by", _uuid_type(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_recruiter_candidate_assignments_recruiter_user_id",
        "recruiter_candidate_assignments",
        ["recruiter_user_id"],
    )
    op.create_index(
        "ix_recruiter_candidate_assignments_candidate_user_id",
        "recruiter_candidate_assignments",
        ["candidate_user_id"],
    )
    op.create_unique_constraint(
        "uq_recruiter_candidate_assignment",
        "recruiter_candidate_assignments",
        ["recruiter_user_id", "candidate_user_id"],
    )
    op.create_foreign_key(
        "fk_rca_recruiter_user_id_users", "recruiter_candidate_assignments",
        "users", ["recruiter_user_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_rca_candidate_user_id_users", "recruiter_candidate_assignments",
        "users", ["candidate_user_id"], ["id"], ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_rca_assigned_by_users", "recruiter_candidate_assignments",
        "users", ["assigned_by"], ["id"], ondelete="SET NULL",
    )
    # New permission gate for this chunk's write endpoints.
    op.execute(
        "INSERT INTO permissions (id, resource, action, description) "
        "SELECT gen_random_uuid(), 'recruiter_assignments', 'write', "
        "'Assign/unassign candidates to recruiters' "
        "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE resource='recruiter_assignments' AND action='write')"
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM permissions WHERE resource='recruiter_assignments' AND action='write'"
    )
    op.drop_constraint("fk_rca_assigned_by_users", "recruiter_candidate_assignments", type_="foreignkey")
    op.drop_constraint("fk_rca_candidate_user_id_users", "recruiter_candidate_assignments", type_="foreignkey")
    op.drop_constraint("fk_rca_recruiter_user_id_users", "recruiter_candidate_assignments", type_="foreignkey")
    op.drop_constraint("uq_recruiter_candidate_assignment", "recruiter_candidate_assignments", type_="unique")
    op.drop_index("ix_recruiter_candidate_assignments_candidate_user_id", table_name="recruiter_candidate_assignments")
    op.drop_index("ix_recruiter_candidate_assignments_recruiter_user_id", table_name="recruiter_candidate_assignments")
    op.drop_table("recruiter_candidate_assignments")
```

The raw-SQL permission seed's `gen_random_uuid()` is Postgres-specific — check how
`046_admin_seed_module4_permissions.py` seeds rows across both dialects (this repo's dual
SQLite/Postgres support per ADR 0002) and copy its exact insert mechanics/UUID-generation
approach instead of assuming `gen_random_uuid()` works on SQLite; the snippet above is
illustrative of *what* row to insert, not the final cross-dialect-safe SQL.

## Ambiguities resolved

- **Pool-with-assignment vs. access-restrictive assignment: this was deliberately discussed and
  resolved as pool-with-assignment.** The naive reading of "recruiter-candidate assignment"
  could imply a recruiter should only see/work their assigned candidates (an access-control
  gate). That design was explicitly rejected for this product: there is one shared candidate
  pool (per `machine-1-tenancy-core/00-overview.md`'s brand model — brands are presentation-only,
  not tenancy boundaries), and restricting candidate visibility by assignment would reintroduce
  exactly the kind of artificial silo the brand-model pivot removed. Assignment here is a
  bookkeeping/workload/notification-routing marker only. Any future request to make this
  access-restrictive is a distinct, materially different feature (effectively a mini
  tenancy-within-a-tenancy) — do not casually reinterpret this table's purpose that way without a
  new explicit decision.
- **Can a candidate have more than one assigned recruiter at once?** Yes — the unique constraint
  is on the `(recruiter, candidate)` pair, not on `candidate_user_id` alone. This allows
  temporary co-ownership during handoffs without a data model change; a "primary recruiter"
  concept, if wanted later, is out of scope here (no `is_primary` column added speculatively).
- **Does unassigning a candidate delete their history/notes elsewhere?** No — this table has no
  cascading relationship to any other domain data. Deleting a `RecruiterCandidateAssignment` row
  only affects the "my candidates" view and notification routing; it never deletes or hides any
  `JobMatch`, `OutreachMessage`, `CandidateDocument`, etc.

## Do not touch

- `backend/app/modules/job_matching/`, `backend/app/modules/outreach/`,
  `backend/app/modules/documents/`, `backend/app/modules/job_swipe/` — none of these modules'
  existing list/search/query functions are edited to add a `recruiter_user_id`-based filter. This
  is the single most important boundary in this chunk (see Goal section).
- `backend/app/auth/models.py` — no new column added to `User`; assignment is a separate join
  table, not a `User.assigned_recruiter_id` column (which would only support one recruiter per
  candidate, contradicting the "co-ownership allowed" decision above).
- Do not build the workload-reporting dashboard or the notification-dispatch logic itself in
  this chunk — only the read paths (`list_assignments_for_recruiter`,
  `list_assigned_recruiters_for_candidate`) that those future features would call.

## Verification

- Test: `assign_candidate` creates a row; calling it again with the same
  `(recruiter_user_id, candidate_user_id)` pair does not 500 (idempotent, returns/references the
  existing row).
- Test: `unassign_candidate` on a non-existent assignment is a no-op (does not 404/500).
- Test: `list_my_candidates` for recruiter A does not include an assignment belonging to
  recruiter B.
- **Access-control regression test (release-blocking for this chunk):** with no
  `RecruiterCandidateAssignment` row linking recruiter A to candidate C, assert recruiter A can
  still successfully call an existing, unrelated candidate-scoped endpoint (e.g. viewing
  candidate C's job matches or outreach messages, via whatever existing endpoint a
  recruiter/admin-role caller can already reach today) — i.e. assert this chunk introduces zero
  new 403s anywhere outside its own new router.
- Test: `POST /api/recruiter-assignments` 403s for a caller lacking
  `recruiter_assignments:write` (unless also `is_superuser` or exempted per the router's chosen
  self-unassign shape).
