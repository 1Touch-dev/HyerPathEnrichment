# Machine 2, Track 11 — Per-Brand Chatbot Config

## Depends on

`machine-1-tenancy-core/02-schema-and-migration.md`'s `Brand` model (the renamed
`Organization` — presentation-only: name, slug, custom_domain, chatbot config, landing-page tier)
and its `users.signup_brand_id` column (nullable FK to `brands.id`, presentation-only, no query
filtering). This chunk cannot land its own migration until `brands`/`users.signup_brand_id`
actually exist as real tables/columns — verify both exist in the real schema before writing this
chunk's migration's `down_revision`. Also depends on the existing CV-completeness chatbot,
`backend/app/modules/documents/cv_chat_service.py`'s `CvChatService`, which this chunk extends
in place rather than replacing.

## Naming correction (apply throughout this file)

There is no separate `candidates` table — the brand-attribution column lives on `users` as
`users.signup_brand_id`, not `candidates.signup_brand_id`.

## Goal

Each `Brand` row gets its own chatbot customization (system-prompt additions, tone, brand
name/voice) that applies when the CV-completeness chatbot (`CvChatService`) talks to a candidate
who signed up through that brand's storefront (i.e. whose `users.signup_brand_id` points at that
brand). A candidate with `signup_brand_id IS NULL` (signed up directly, no brand storefront) gets
the existing default chatbot behavior, completely unchanged — this chunk is additive only, never
a behavior change for the no-brand case.

This is presentation/tone customization only — it does not change *what* the chatbot asks about
(the missing-fields-driven question flow from `compute_missing_fields`/`question_for_field` is
untouched) or *which* fields it can write back (`_apply_field_value`'s field-name allowlist is
untouched). It only changes the system prompt's brand-voice framing and, optionally, a
brand-specific greeting/tone instruction layered on top of the existing per-field system prompt.

## Files to create

- `backend/alembic/versions/052_brand_chatbot_config.py` (verify real next number — third new
  chunk in this batch wanting a `05x` slot alongside `08`'s `050_*` and `09`'s `051_*`; re-run
  `python -m alembic heads` before writing `down_revision`)

## Files to edit

- `backend/app/modules/brands/models.py` (or wherever `Brand` actually landed — per `02`'s
  file-path convention, likely `backend/app/modules/brands/models.py`; **verify the real path
  and class name from `machine-1-tenancy-core/02-schema-and-migration.md`'s final file listing
  before editing**, since this doc set's `Organization`->`Brand` rename may have landed under a
  different module directory name than `orgs/` originally specced)
- `backend/app/clients/llm_tools.py` — extend `build_chat_system_prompt`.
- `backend/app/modules/documents/cv_chat_service.py` — resolve and pass brand config through.

## `Brand` model edit — new column

Add to the `Brand` model (wherever it lives post-`02`), following the JSON-config-column
convention already established by `FeatureFlag.value` in `backend/app/modules/admin/models.py`
(`Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)`):

```python
    # Per-brand chatbot customization (machine-2/11): system-prompt additions,
    # tone, and brand voice applied when CvChatService talks to a candidate whose
    # users.signup_brand_id points at this brand. NULL means "no customization" —
    # falls back to the existing default chatbot behavior identically to a
    # candidate with signup_brand_id IS NULL entirely (see 11's Goal section for
    # why both cases must behave identically). Shape (validated at the
    # schema/service layer, not a DB constraint, matching FeatureFlag.value's own
    # unconstrained-JSON convention):
    # {"brand_voice_name": str, "tone": str, "system_prompt_addition": str}
    chatbot_config: Mapped[dict[str, Any] | None] = mapped_column(JsonDoc, nullable=True)
```

If `Brand` already gained a `chatbot_config` column as part of `02`'s own schema rewrite (per the
brand-model plan's Goal section listing "chatbot config" as one of `Brand`'s presentation
attributes alongside name/slug/custom_domain/landing_page tier), **do not add a duplicate column**
— check `02`'s actual landed file first; if the column already exists with a different shape than
above, this chunk should conform to whatever `02` already defined rather than overwriting it,
and this section becomes a no-op (flag this in the implementer's own report if so, rather than
silently reshaping an existing column).

## `backend/app/clients/llm_tools.py` — `build_chat_system_prompt` extension

Locate the existing `build_chat_system_prompt(field_name, question)` function (imported by
`cv_chat_service.py` today) and add an optional third parameter:

```python
def build_chat_system_prompt(
    field_name: str, question: str, brand_config: dict[str, Any] | None = None
) -> str:
    """Existing per-field system prompt (unchanged base behavior), optionally
    prefixed with a brand-voice framing line when brand_config is provided.
    brand_config=None (the default, and the only value ever passed for a
    candidate with signup_brand_id IS NULL or a brand with chatbot_config IS
    NULL) must produce byte-identical output to this function's pre-existing
    behavior — see 11's Verification section's regression requirement."""
    base_prompt = ...  # existing body, unchanged — read the real current
                        # implementation before editing; do not restructure it,
                        # only prepend to its return value conditionally

    if not brand_config:
        return base_prompt

    voice_name = brand_config.get("brand_voice_name", "").strip()
    tone = brand_config.get("tone", "").strip()
    addition = brand_config.get("system_prompt_addition", "").strip()

    brand_lines = []
    if voice_name:
        brand_lines.append(f"You are speaking as {voice_name}'s CV assistant.")
    if tone:
        brand_lines.append(f"Tone: {tone}.")
    if addition:
        brand_lines.append(addition)

    if not brand_lines:
        return base_prompt
    return f"{' '.join(brand_lines)}\n\n{base_prompt}"
```

Read the real current `build_chat_system_prompt` implementation in full before writing this edit
— the snippet above shows the *pattern* (optional param, no-op when absent, prepend when
present), not a verbatim diff against unseen code.

## `backend/app/modules/documents/cv_chat_service.py` — resolving which brand config to use

In `_call_llm_with_tool` (the only call site of `build_chat_system_prompt` today), thread the
candidate's brand config through:

```python
    async def _call_llm_with_tool(
        self, field_name: str, question: str, candidate_reply: str, user_id: UUID
    ) -> tuple[str, str] | None:
        """... existing docstring ..."""
        brand_config = await self._resolve_brand_chatbot_config(user_id)
        ...
        payload = {
            ...
            "messages": [
                {
                    "role": "system",
                    "content": build_chat_system_prompt(field_name, question, brand_config),
                },
                {"role": "user", "content": candidate_reply},
            ],
            ...
        }
```

Add the resolution helper:

```python
    async def _resolve_brand_chatbot_config(self, user_id: UUID) -> dict[str, Any] | None:
        """Loads the candidate's users.signup_brand_id, then that Brand's
        chatbot_config, if both exist. Returns None (falls back to default
        chatbot behavior) when: the user has no signup_brand_id, the referenced
        Brand row is missing/inactive, or chatbot_config itself is NULL/empty —
        all three cases must produce identical (no customization) behavior, not
        three different fallback shapes."""
        result = await self.db.execute(select(User.signup_brand_id).where(User.id == user_id))
        brand_id = result.scalar_one_or_none()
        if brand_id is None:
            return None
        brand_result = await self.db.execute(
            select(Brand.chatbot_config, Brand.is_active).where(Brand.id == brand_id)
        )
        row = brand_result.one_or_none()
        if row is None or not row.is_active:
            return None
        return row.chatbot_config or None
```

Thread `user_id` into `_call_llm_with_tool`'s one call site (`post_message`, which already has
`session.user_id` in scope from `_get_owned_session`) — this is a signature-only change to an
existing private method, following the same "thread an existing in-scope value through an
internal signature" convention `07-demand-intelligence-resume-integration.md` already used for
threading `db: AsyncSession` into `_draft_with_llm`.

Import `Brand` from wherever `02` actually placed it (`from app.modules.brands.models import
Brand` or the real equivalent path — verify before writing) and `User` from
`app.auth.models` (already imported elsewhere in this codebase's convention for cross-module
read-only lookups).

## Migration: `052_brand_chatbot_config.py`

Only needed if `Brand.chatbot_config` does not already exist per `02`'s own migration (see the
model-edit section's caveat above). If it is genuinely new:

```python
def upgrade() -> None:
    op.add_column("brands", sa.Column("chatbot_config", JsonDoc_equivalent, nullable=True))


def downgrade() -> None:
    op.drop_column("brands", "chatbot_config")
```

Use whatever this repo's actual dual-SQLite/Postgres JSON column type convention is (check
`JsonDoc`'s definition in `app/database/base.py` and how an existing migration adds a JSON column
across both dialects, e.g. `045_admin_module3_moderation_columns.py` or similar, rather than
assuming a specific `sa.JSON`/`postgresql.JSONB` split without checking).

## Ambiguities resolved

- **Does a brand's chatbot config affect anything besides the CV-completeness chatbot?** No —
  scoped strictly to `CvChatService`. If this repo later adds other LLM-facing candidate touch
  points (resume tailoring's `10`, outreach drafting), those are separate features with their own
  system prompts; this chunk does not wire brand config into either of them. A future chunk could
  choose to reuse the same `chatbot_config` shape for those, but that is an explicit future
  decision, not implied by this one.
- **What if a candidate's `signup_brand_id` points at a brand that's since been deactivated
  (`is_active=False`, per `post-tenancy-features/03-org-offboarding-and-deletion.md`'s brand
  deactivation)?** Falls back to default (no customization) — `_resolve_brand_chatbot_config`
  checks `is_active` explicitly above. This keeps chatbot behavior sane for a candidate whose
  original signup brand has since been shut down, without needing to null out their historical
  `signup_brand_id` (which stays presentation-only/historical per `02`'s own design, unaffected by
  brand deactivation).
- **Should brand config be candidate-editable?** No — it is a brand-level (not user-level)
  setting, edited by whoever manages `Brand` rows (an admin-facing brand-management surface is
  out of scope for this chunk; this chunk only adds the column and the chat-service's read path,
  not a new admin CRUD UI for editing `chatbot_config` itself — an operator can set it directly
  via migration/DB today, same bootstrapping convention `FeatureFlag` rows use before any
  CRUD UI existed for them).

## Do not touch

- `backend/app/domain/cv_completeness.py` — `compute_missing_fields`/`question_for_field` are
  untouched; brand config never changes which fields are asked about or in what order.
- `cv_chat_service.py`'s `_apply_field_value` — the field-name allowlist and value-parsing logic
  is untouched; brand config affects prompt framing only, never what gets written back to
  `extracted_data`.
- Do not add a `Brand`-scoping filter to any candidate-listing/search query anywhere in the
  codebase as part of this chunk — `signup_brand_id` remains presentation-only per `02`'s
  decision; this chunk's brand lookup is read-only, one row, keyed by the candidate's own
  `signup_brand_id`, not a basis for filtering which candidates anyone can see.
- `backend/app/modules/documents/router.py`, `schemas.py` — no new request/response field;
  brand-config resolution is entirely internal to `CvChatService`, invisible to the API contract
  (a candidate/recruiter reviewing chat history sees the same `CvChatMessageResponse` shape as
  before this chunk).

## Verification

- Test: a candidate with `signup_brand_id IS NULL` produces a system prompt byte-identical to
  this chunk's pre-existing behavior (regression check, mirroring `07`'s own
  byte-identical-when-disabled requirement).
- Test: a candidate with `signup_brand_id` pointing at a `Brand` whose `chatbot_config IS NULL`
  also produces the byte-identical default prompt.
- Test: a candidate with `signup_brand_id` pointing at a `Brand` with a populated
  `chatbot_config` (all three of `brand_voice_name`/`tone`/`system_prompt_addition` set) produces
  a system prompt containing the expected brand-voice prefix ahead of the unchanged base prompt.
- Test: a candidate whose `signup_brand_id` points at a `Brand` with `is_active=False` falls back
  to the default prompt (not the brand's config), even if that brand's `chatbot_config` is
  populated.
- Test: `_resolve_brand_chatbot_config` performs at most one extra query per chat turn (assert
  query count, not just correctness) — this chunk should not introduce an N+1 or repeated lookup
  pattern into a chat loop that already runs once per candidate reply.
