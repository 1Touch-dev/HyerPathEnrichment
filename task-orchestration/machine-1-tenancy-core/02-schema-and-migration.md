# Machine 1, Chunk 2 — Schema and Migration

## Depends on

Chunk `01`'s ADR decision (column-based tenancy, one org per user, nullable `org_id`). Re-read
`docs/adr/0018-tenancy-model.md` (or whatever number it landed as) before implementing if it is
not fresh in context.

## Files to create

- `backend/app/modules/orgs/__init__.py`
- `backend/app/modules/orgs/models.py`
- `backend/app/modules/orgs/schemas.py`
- `backend/app/modules/orgs/repository.py`
- `backend/alembic/versions/047_create_organizations_and_user_org_id.py`

## Files to edit

- `backend/app/auth/models.py` — add `org_id` column to `User`.
- `backend/app/database/base.py` — **only if** it maintains an explicit list/registry of ORM
  modules that must be imported for Alembic autogenerate/metadata discovery to see new tables
  (check how `app.modules.admin.models` or `app.modules.portfolio.models` currently get
  registered — likely via `app/database/session.py` or a central import list — and follow that
  exact existing pattern rather than inventing a new registration mechanism).

## `backend/app/modules/orgs/models.py`

```python
"""ORM models for the placement-agency tenancy layer (Decision: docs/adr/0018-tenancy-model.md)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Organization(Base):
    """A tenant: one placement agency. Recruiters (`User` rows) belong to at most
    one Organization via `User.org_id`. See docs/adr/0018-tenancy-model.md for why
    this is column-based tenancy, not schema-per-tenant."""

    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    # Custom CORS origin for this org's branded frontend, e.g. "https://acme.hyrepath.com".
    # NULL means this org has no dedicated origin and relies on the platform default
    # (see machine-1-tenancy-core/04-cors-and-ratelimit-retrofit.md).
    custom_origin: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
```

`slug` is the URL-safe identifier used later by `post-tenancy-features/02-brand-landing-pages.md`
for subdomain routing (`{slug}.hyrepath.com`) — defining it now avoids a second migration later
purely to add a column that both future consumers need.

## `backend/app/modules/orgs/schemas.py`

Pydantic request/response models, following the exact pattern in
`backend/app/modules/portfolio/schemas.py` (check that file's import style —
`from pydantic import BaseModel, Field` plus `model_config = ConfigDict(from_attributes=True)`
on response models). Minimum required:

```python
class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9-]+$")


class OrganizationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    custom_origin: str | None
    is_active: bool
    created_at: datetime
```

No router/service in this chunk — CRUD endpoints for org management are
`machine-2-parallel-tracks/04-rbac-admin-platform.md`'s responsibility (it extends admin with
org-management routes once this schema exists). This chunk only needs the schema module to exist
so chunk `03` (JWT claim) and `04-rbac-admin-platform.md` can both import
`OrganizationResponse` without duplicating it.

## `backend/app/modules/orgs/repository.py`

Minimal, following the pattern in `backend/app/modules/portfolio/repository.py` (plain async
functions taking `db: AsyncSession`, not a class):

```python
async def get_organization_by_id(db: AsyncSession, org_id: UUID) -> Organization | None: ...
async def get_organization_by_slug(db: AsyncSession, slug: str) -> Organization | None: ...
async def create_organization(db: AsyncSession, name: str, slug: str) -> Organization: ...
```

## `backend/app/auth/models.py` edit

Add this column to the `User` class, placed directly after the existing
`# Admin Module: RBAC role assignment + MFA` block (after `mfa_enrolled_at`, before
`# Email verification`) so related identity/authorization columns stay grouped:

```python
    # Tenancy (docs/adr/0018-tenancy-model.md): NULL means "no org / legacy direct
    # user" — not backfilled to a synthetic default org. See that ADR's Decision §3.
    org_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
```

This requires adding `from app.modules.orgs.models import Organization` — or, to avoid a circular
import (`orgs` doesn't need to import `auth`, so this direction is safe) — a `TYPE_CHECKING`-only
import is not required here since the FK target is a table name string (`"organizations.id"`),
not a Python class reference; only add the import if you also add a `relationship()` (optional,
not required for this chunk — the retrofit chunks and `04-rbac-admin-platform.md` can query by
`org_id` directly without an ORM relationship).

## `backend/alembic/versions/047_create_organizations_and_user_org_id.py`

Follow the exact header/revision-id/downgrade conventions in `046_admin_seed_module4_permissions.py`
(revision id is the filename stem, `down_revision` points to the current single head,
`branch_labels`/`depends_on` are `None`). Current head at time of writing is
`046_admin_seed_module4_permissions` — **verify this is still the head** by running
`python -m alembic heads` from `backend/` before writing `down_revision`; if another migration has
landed in the meantime, point `down_revision` at whatever the actual current head is instead.

```python
"""Create organizations table and add users.org_id (Decision: docs/adr/0018-tenancy-model.md).

Revision ID: 047_create_organizations_and_user_org_id
Revises: 046_admin_seed_module4_permissions
Create Date: 2026-08-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "047_create_organizations_and_user_org_id"
down_revision: str | Sequence[str] | None = "046_admin_seed_module4_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid_type():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return postgresql.UUID(as_uuid=True)
    return sa.String(36)


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", _uuid_type(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("custom_origin", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_unique_constraint("uq_organizations_slug", "organizations", ["slug"])
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    op.add_column("users", sa.Column("org_id", _uuid_type(), nullable=True))
    op.create_index("ix_users_org_id", "users", ["org_id"])
    op.create_foreign_key(
        "fk_users_org_id_organizations",
        "users",
        "organizations",
        ["org_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_users_org_id_organizations", "users", type_="foreignkey")
    op.drop_index("ix_users_org_id", table_name="users")
    op.drop_column("users", "org_id")
    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_constraint("uq_organizations_slug", "organizations", type_="unique")
    op.drop_table("organizations")
```

Note the `_uuid_type()` helper mirrors the existing dual-dialect pattern in
`046_admin_seed_module4_permissions.py` (Postgres UUID vs. SQLite-compatible `String(36)`) — this
repo's local dev runs SQLite while Docker/prod runs Postgres (ADR 0002), so every migration must
support both dialects the same way existing migrations do.

## Ambiguities resolved

- **Should `org_id` be backfilled onto existing users into a "default" org?** No — per the ADR's
  Decision §3, `NULL` explicitly means "no org." Do not write a data-migration step that creates
  a default org and backfills existing rows; that would contradict the ADR this chunk depends on.
- **Should this chunk also add a `user_organizations` join table for future multi-org
  membership?** No — the ADR explicitly chose single-FK-per-user for v1 (Decision §2). Do not
  add a join table speculatively.

## Verification

From `backend/`:

```bash
python -m alembic upgrade head
python -m alembic downgrade -1   # confirm downgrade doesn't error
python -m alembic upgrade head
```

Run this against **both** SQLite (default local `.env`) and, if Docker is available locally,
against the Postgres service (`docker compose -f docker/docker-compose.yml up postgres -d`, then
point `DATABASE_URL` at it) — the dual-dialect `_uuid_type()` helper is exactly the kind of code
that silently works on one dialect and breaks on the other.

## Do not touch

- No changes to `job_matching`, `outreach`, `documents`, `portfolio`, or `admin` models/tables in
  this chunk.
- Do not create any router/service for `orgs` in this chunk (see "Files to create" — router is
  explicitly out of scope here, owned by `machine-2-parallel-tracks/04-rbac-admin-platform.md`).
- Do not touch `backend/app/auth/router.py`, `backend/app/auth/dependencies.py`, or any JWT
  encode/decode logic — that is chunk `03`.
