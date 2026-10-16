"""Add Portfolio Studio draft/published revision columns.

Revision ID: 067_portfolio_studio
Revises: 066_privileged_idempotency_records
Create Date: 2026-10-16

Backfills existing profiles from legacy headline/bio/items into draft_revision
(and published_revision when already published).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql import column, select, table

from alembic import op

revision: str = "067_portfolio_studio"
down_revision: str | Sequence[str] | None = "066_privileged_idempotency_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SECTION_KEYS = (
    "about",
    "projects",
    "experience",
    "education",
    "skills",
    "certifications",
    "social",
    "contact",
)


def _json_type() -> sa.types.TypeEngine:
    if op.get_bind().dialect.name == "postgresql":
        return postgresql.JSONB()
    return sa.JSON()


def _empty_revision() -> dict[str, Any]:
    return {
        "template_id": "minimal_professional",
        "theme": {"palette": "neutral", "accent": None, "font_pairing": "sans"},
        "content": {
            "display_name": None,
            "professional_role": None,
            "location": None,
            "headline": None,
            "summary": None,
            "about": None,
            "profile_image_url": None,
            "cover_image_url": None,
            "email": None,
            "resume_url": None,
            "projects": [],
            "experience": [],
            "education": [],
            "skills": [],
            "certifications": [],
            "social_links": [],
        },
        "section_visibility": {key: True for key in SECTION_KEYS},
        "section_order": list(SECTION_KEYS),
    }


def _revision_from_row(
    *,
    display_name: str | None,
    headline: str | None,
    bio: str | None,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    revision = _empty_revision()
    content = revision["content"]
    content["display_name"] = display_name
    content["headline"] = headline
    content["summary"] = bio
    content["about"] = bio
    projects: list[dict[str, Any]] = []
    social: list[dict[str, Any]] = []
    for idx, item in enumerate(items):
        item_type = item.get("item_type") or "other"
        title = item.get("title") or "Link"
        url = item.get("url") or ""
        description = item.get("description")
        image_url = item.get("image_url")
        order = item.get("display_order") if item.get("display_order") is not None else idx
        project = {
            "id": str(item.get("id") or f"migrated-{idx}"),
            "title": title,
            "description": description,
            "image_url": image_url,
            "tech_stack": [],
            "demo_url": None if item_type == "github" else (url or None),
            "repo_url": url if item_type == "github" else None,
            "display_order": order,
        }
        projects.append(project)
        if item_type == "github" and url:
            social.append(
                {
                    "id": f"social-{idx}",
                    "platform": "github",
                    "label": title,
                    "url": url,
                    "display_order": order,
                }
            )
    content["projects"] = projects
    content["social_links"] = social
    return revision


def upgrade() -> None:
    json_type = _json_type()
    op.add_column(
        "portfolio_profiles",
        sa.Column(
            "draft_revision",
            json_type,
            nullable=False,
            server_default=sa.text("'{}'" if op.get_bind().dialect.name == "postgresql" else "'{}'"),
        ),
    )
    op.add_column(
        "portfolio_profiles",
        sa.Column("published_revision", json_type, nullable=True),
    )

    bind = op.get_bind()
    profiles = table(
        "portfolio_profiles",
        column("id", sa.String),
        column("display_name", sa.String),
        column("headline", sa.String),
        column("bio", sa.Text),
        column("is_published", sa.Boolean),
        column("draft_revision", json_type),
        column("published_revision", json_type),
    )
    items_t = table(
        "portfolio_items",
        column("id", sa.String),
        column("profile_id", sa.String),
        column("item_type", sa.String),
        column("title", sa.String),
        column("description", sa.Text),
        column("url", sa.String),
        column("image_url", sa.String),
        column("display_order", sa.Integer),
    )

    profile_rows = bind.execute(
        select(
            profiles.c.id,
            profiles.c.display_name,
            profiles.c.headline,
            profiles.c.bio,
            profiles.c.is_published,
        )
    ).fetchall()

    for row in profile_rows:
        profile_id = row[0]
        item_rows = bind.execute(
            select(
                items_t.c.id,
                items_t.c.item_type,
                items_t.c.title,
                items_t.c.description,
                items_t.c.url,
                items_t.c.image_url,
                items_t.c.display_order,
            ).where(items_t.c.profile_id == profile_id)
        ).fetchall()
        items = [
            {
                "id": str(ir[0]),
                "item_type": ir[1],
                "title": ir[2],
                "description": ir[3],
                "url": ir[4],
                "image_url": ir[5],
                "display_order": ir[6],
            }
            for ir in item_rows
        ]
        rev = _revision_from_row(
            display_name=row[1],
            headline=row[2],
            bio=row[3],
            items=items,
        )
        # Store as JSON text for SQLite compatibility when using JSON type.
        payload: Any = rev
        if bind.dialect.name != "postgresql":
            payload = json.dumps(rev)
        update_values: dict[str, Any] = {"draft_revision": payload}
        if row[4]:
            update_values["published_revision"] = payload
        bind.execute(profiles.update().where(profiles.c.id == profile_id).values(**update_values))

    # Drop server default after backfill so app-level defaults own the value.
    if bind.dialect.name == "postgresql":
        op.alter_column("portfolio_profiles", "draft_revision", server_default=None)


def downgrade() -> None:
    op.drop_column("portfolio_profiles", "published_revision")
    op.drop_column("portfolio_profiles", "draft_revision")
