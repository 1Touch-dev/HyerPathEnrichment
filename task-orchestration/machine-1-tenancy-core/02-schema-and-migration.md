# Machine 1, Chunk 2 — Schema and Migration

## Depends on

Chunk `01`'s ADR decision (`Brand` as a normal, unscoped table; no access-scoping column on
`users`; `signup_brand_id` and `recruiter_candidate_assignments` are presentation/ownership-only,
never query filters). Re-read `docs/adr/0018-tenancy-model.md` (or whatever number it landed as)
before implementing if it is not fresh in context.

## Files to create

- `backend/app/modules/brands/__init__.py`
- `backend/app/modules/brands/models.py`
- `backend/app/modules/brands/schemas.py`
- `backend/app/modules/brands/repository.py`
- `backend/alembic/versions/047_create_brands_and_candidate_assignments.py`

## Files to edit

- `backend/app/auth/models.py` — add `signup_brand_id` column to `User`. **Do not** add any
  `org_id`/`brand_id`/`tenant_id` access-scoping column anywhere in this chunk — see the ADR's
  Decision §2.
- `backend/app/database/base.py` — **only if** it maintains an explicit list/registry of ORM
  modules that must be imported for Alembic autogenerate/metadata discovery to see new tables
  (check how `app.modules.admin.models` or `app.modules.portfolio.models` currently get
  registered — likely via `app/database/session.py` or a central import list — and follow that
  exact existing pattern rather than inventing a new registration mechanism).

## `backend/app/modules/brands/models.py`

```python
"""ORM models for Brand: a presentation-only storefront concept
(Decision: docs/adr/0018-tenancy-model.md). Brand is NOT a data-isolation boundary — no
query anywhere filters by brand_id, and no code path uses Brand to decide who can see
what. It exists purely to drive custom-domain routing, per-brand chatbot config, and
landing-page tier presentation on top of the one shared candidate/recruiter pool."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, JsonDoc


class Brand(Base):
    """A branded storefront: name, slug, optional custom domain, chatbot config,
    landing-page tier config. Never an FK target for any access-control decision —
    see docs/adr/0018-tenancy-model.md's Decision §1."""

    __tablename__ = "brands"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    # Custom domain for this brand's storefront, e.g. "careers.acme.com". NULL means
    # this brand has no dedicated domain and is only reachable via the platform's
    # default host + /b/{slug} routing (see post-tenancy-features/02-brand-landing-
    # pages.md). Used only for CORS origin resolution (machine-1-tenancy-core/
    # 04-cors-and-ratelimit-retrofit.md) and storefront routing — never a query filter.
    custom_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Per-brand prompt/tone/branding overrides for the CV-chat service. See
    # machine-2-parallel-tracks/11-per-brand-chatbot-config.md for the schema this
    # JSON blob follows; this chunk only reserves the column.
    chatbot_config: Mapped[dict | None] = mapped_column(JsonDoc, nullable=True)
    # Which landing-page tier/segment sub-pages this brand exposes (e.g. which of
    # post-tenancy-features/02-brand-landing-pages.md's /b/{slug}/{tier} pages are
    # enabled and their tier-specific copy/config). This chunk only reserves the
    # column; that chunk owns the actual shape.
    landing_page_tier_config: Mapped[dict | None] = mapped_column(JsonDoc, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class RecruiterCandidateAssignment(Base):
    """Ownership/responsibility marker only — many-to-many. Recording or omitting a
    row here has NO effect on which candidates a recruiter can search, view, or act
    on; every recruiter can already work every candidate in the shared pool. This
    table exists solely to back "my assigned candidates" views and reporting. See
    docs/adr/0018-tenancy-model.md's Decision §4 — do not add an authorization check
    anywhere that reads this table."""

    __tablename__ = "recruiter_candidate_assignments"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    recruiter_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

`RecruiterCandidateAssignment` needs `from sqlalchemy import ForeignKey` added to the imports
above alongside `Boolean, DateTime, String`. Add a composite unique constraint on
`(recruiter_user_id, candidate_user_id)` via `__table_args__` so the same pair can't be recorded
twice — that's a data-hygiene constraint, not an access-control one:

```python
    __table_args__ = (
        UniqueConstraint(
            "recruiter_user_id", "candidate_user_id", name="uq_recruiter_candidate_assignment"
        ),
    )
```

`slug` on `Brand` is the URL-safe identifier used later by
`post-tenancy-features/02-brand-landing-pages.md` for `/b/{slug}` routing — defining it now avoids
a second migration later purely to add a column that consumer needs.

## `backend/app/modules/brands/schemas.py`

Pydantic request/response models, following the exact pattern in
`backend/app/modules/portfolio/schemas.py` (check that file's import style —
`from pydantic import BaseModel, Field` plus `model_config = ConfigDict(from_attributes=True)`
on response models). Minimum required:

```python
class BrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")
    custom_domain: str | None = None
    chatbot_config: dict | None = None
    landing_page_tier_config: dict | None = None


class BrandResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    custom_domain: str | None
    chatbot_config: dict | None
    landing_page_tier_config: dict | None
    is_active: bool
    created_at: datetime
```

No router/service in this chunk — CRUD endpoints for brand management are
`machine-2-parallel-tracks/04-rbac-admin-platform.md`'s responsibility, same as this doc set's
prior `orgs` scaffold. This chunk only needs the schema module to exist so
`04-rbac-admin-platform.md`, `machine-2-parallel-tracks/11-per-brand-chatbot-config.md`, and
`post-tenancy-features/02-brand-landing-pages.md` can all import `BrandResponse` without
duplicating it.

## `backend/app/modules/brands/repository.py`

Minimal, following the pattern in `backend/app/modules/portfolio/repository.py` (plain async
functions taking `db: AsyncSession`, not a class):

```python
async def get_brand_by_id(db: AsyncSession, brand_id: UUID) -> Brand | None: ...
async def get_brand_by_slug(db: AsyncSession, slug: str) -> Brand | None: ...
async def create_brand(db: AsyncSession, **fields) -> Brand: ...
async def list_active_brands(db: AsyncSession) -> list[Brand]: ...

async def create_assignment(
    db: AsyncSession, *, recruiter_user_id: UUID, candidate_user_id: UUID
) -> RecruiterCandidateAssignment:
    """Idempotent by (recruiter_user_id, candidate_user_id) — return the existing row
    if the pair is already assigned rather than raising a unique-constraint error.
    Used by machine-2-parallel-tracks/08-recruiter-candidate-assignment.md."""
    ...

async def list_assigned_candidate_ids(db: AsyncSession, recruiter_user_id: UUID) -> list[UUID]:
    """For 'my assigned candidates' views/reporting only — never used to restrict
    what a recruiter can query elsewhere."""
    ...
```

## `backend/app/auth/models.py` edit

Add this column to the `User` class, placed directly after the existing
`# Admin Module: RBAC role assignment + MFA` block (after `mfa_enrolled_at`, before
`# Email verification`) so related identity/profile columns stay grouped:

```python
    # Brand attribution (docs/adr/0018-tenancy-model.md): which brand storefront this
    # candidate signed up through, if any. Presentation-only — NEVER used to filter
    # any query or restrict which recruiter can act on this candidate. NULL means
    # signed up directly (no storefront), or predates the Brand concept.
    signup_brand_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("brands.id", ondelete="SET NULL"), nullable=True, index=True
    )
```

The doc set's informal "candidates" language (e.g. `candidates.signup_brand_id`) refers to `User`
rows without a staff/recruiter role — there is no separate `candidates` table in this schema (see
`app/domain/candidate.py`'s `CVData`, which is a Pydantic extraction shape, not an ORM table).
The real column lives on `users`, exactly like every other candidate-facing column already does.

This requires adding `from app.modules.brands.models import Brand` — or, to avoid a circular
import (`brands` doesn't need to import `auth`, so this direction is safe) — a `TYPE_CHECKING`-
only import is not required here since the FK target is a table name string (`"brands.id"`), not
a Python class reference; only add the import if you also add a `relationship()` (optional, not
required for this chunk).

## `backend/alembic/versions/047_create_brands_and_candidate_assignments.py`

Follow the exact header/revision-id/downgrade conventions in `046_admin_seed_module4_permissions.py`
(revision id is the filename stem, `down_revision` points to the current single head,
`branch_labels`/`depends_on` are `None`). **Stale note, corrected 2026-08-26:** this section
originally said the head was `046_admin_seed_module4_permissions`; the Machine-2 merge (PR #255)
has since landed 5 more migrations, so the real current single head, verified today, is
`051_merge_machine2_parallel_track_heads`. **Verify this is still the head** by running
`python -m alembic heads` from `backend/` before writing `down_revision` regardless — if another migration has
landed in the meantime, point `down_revision` at whatever the actual current head is instead.

```python
"""Create brands table, users.signup_brand_id, and recruiter_candidate_assignments
(Decision: docs/adr/0018-tenancy-model.md).

Revision ID: 047_create_brands_and_candidate_assignments
Revises: 046_admin_seed_module4_permissions
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "047_create_brands_and_candidate_assignments"
down_revision: str | Sequence[str] | None = "046_admin_seed_module4_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def _json_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.JSONB
    return sa.JSON


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", _uuid_type(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("custom_domain", sa.String(255), nullable=True),
        sa.Column("chatbot_config", _json_type(), nullable=True),
        sa.Column("landing_page_tier_config", _json_type(), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_brands_slug", "brands", ["slug"])
    op.create_index("ix_brands_slug", "brands", ["slug"])

    op.add_column("users", sa.Column("signup_brand_id", _uuid_type(), nullable=True))
    op.create_index("ix_users_signup_brand_id", "users", ["signup_brand_id"])
    op.create_foreign_key(
        "fk_users_signup_brand_id_brands",
        "users",
        "brands",
        ["signup_brand_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "recruiter_candidate_assignments",
        sa.Column("id", _uuid_type(), primary_key=True),
        sa.Column("recruiter_user_id", _uuid_type(), nullable=False),
        sa.Column("candidate_user_id", _uuid_type(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
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
        "fk_rca_recruiter_user_id_users",
        "recruiter_candidate_assignments",
        "users",
        ["recruiter_user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_rca_candidate_user_id_users",
        "recruiter_candidate_assignments",
        "users",
        ["candidate_user_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_table("recruiter_candidate_assignments")
    op.drop_constraint("fk_users_signup_brand_id_brands", "users", type_="foreignkey")
    op.drop_index("ix_users_signup_brand_id", table_name="users")
    op.drop_column("users", "signup_brand_id")
    op.drop_index("ix_brands_slug", table_name="brands")
    op.drop_constraint("uq_brands_slug", "brands", type_="unique")
    op.drop_table("brands")
```

Note the `_uuid_type()`/`_json_type()` helpers mirror the existing dual-dialect pattern in
`046_admin_seed_module4_permissions.py` (Postgres UUID/JSONB vs. SQLite-compatible `String(36)`/
`JSON`) — this repo's local dev runs SQLite while Docker/prod runs Postgres (ADR 0002), so every
migration must support both dialects the same way existing migrations do.

## Ambiguities resolved

- **Should this chunk add any `org_id`/`tenant_id`/`brand_id` access-scoping column to `users` or
  any other table?** No — per the ADR's Decision §2, there is no access-scoping column anywhere
  in this schema. `signup_brand_id` is presentation-only and must never be used in a `WHERE`
  clause that restricts query results.
- **Should `recruiter_candidate_assignments` have a uniqueness constraint stronger than the
  `(recruiter_user_id, candidate_user_id)` pair (e.g. "a candidate can only be assigned to one
  recruiter at a time")?** No — this doc set does not specify exclusive ownership, only an
  ownership/responsibility marker. Multiple recruiters may be assigned to the same candidate
  simultaneously (e.g. a handoff period, or shared coverage); enforcing exclusivity is a product
  decision for a later chunk if ever needed, not assumed here.
- **Does `Brand` need any relationship back to `job_matching`/`outreach`/`documents`/`portfolio`
  tables?** No — see the ADR's Decision §1. `Brand` is only ever referenced from `users.
  signup_brand_id`; no other table gets a brand FK in this chunk.

## Verification

From `backend/`:

```bash
python -m alembic upgrade head
python -m alembic downgrade -1   # confirm downgrade doesn't error
python -m alembic upgrade head
```

Run this against **both** SQLite (default local `.env`) and, if Docker is available locally,
against the Postgres service (`docker compose -f docker/docker-compose.yml up postgres -d`, then
point `DATABASE_URL` at it) — the dual-dialect `_uuid_type()`/`_json_type()` helpers are exactly
the kind of code that silently works on one dialect and breaks on the other.

## Do not touch

- No changes to `job_matching`, `outreach`, `documents`, `portfolio`, or `admin` models/tables in
  this chunk.
- Do not create any router/service for `brands` in this chunk (see "Files to create" — router is
  explicitly out of scope here, owned by `machine-2-parallel-tracks/04-rbac-admin-platform.md`).
- Do not touch `backend/app/auth/router.py`, `backend/app/auth/dependencies.py`, or any JWT
  encode/decode logic — this chunk adds no JWT claim at all (see `03-auth-org-id-claim.md`'s
  stub for why).
- Do not add a `brand_id`/`org_id` column to any table other than `users` (as
  `signup_brand_id`) and `recruiter_candidate_assignments`.
