# Machine 2, Track 3 — Outreach Strategy Dimension

## Goal

Add a **strategy** dimension to outreach drafting — independent of `message_type` (channel:
email/linkedin/generic/custom) — so a recruiter can choose the *approach* a draft takes (e.g.
lead with a concrete value proposition vs. lead with curiosity vs. reference a warm referral)
without that becoming a fifth `message_type`. This chunk is a dependency for `05` (CAN-SPAM
compliance) and `06` (LinkedIn send) — both reuse the `OutreachMessage.strategy` column and the
`OutreachStrategy` literal type this chunk defines.

## Files to edit

- `backend/app/modules/outreach/models.py`
- `backend/app/modules/outreach/schemas.py`
- `backend/app/modules/outreach/service.py`
- `backend/app/workers/tasks/outreach.py`
- `backend/alembic/versions/047_outreach_strategy_dimension.py` (new file — see migration-number
  note below)

## `backend/app/modules/outreach/schemas.py`

Add, next to `OutreachMessageType`:

```python
OutreachStrategy = Literal["direct_pitch", "value_first", "curiosity", "warm_referral"]
```

- `direct_pitch` — states interest and qualifications plainly, asks for a conversation. This is
  today's *implicit* default behavior (the existing `_EMAIL_SYSTEM_PROMPT` etc. in
  `backend/app/workers/tasks/outreach.py` already writes in this style) — making it an explicit
  named strategy rather than "the only option" is this chunk's actual change.
- `value_first` — leads with a specific, concrete way the candidate could help the company
  (referencing the job description/company context), qualifications second.
- `curiosity` — opens with a genuine, specific question about the company/role to invite a reply
  rather than opening with a pitch.
- `warm_referral` — assumes/states a referral or existing connection context; requires the
  candidate to have actually supplied that context (validated in the service layer, mirroring
  how `custom_instruction` is conditionally required today for `message_type="custom"`).

Add `strategy: OutreachStrategy = "direct_pitch"` to `OutreachDraftRequest` (default preserves
current behavior for existing callers/tests that don't pass it) and `strategy: OutreachStrategy`
to `OutreachMessageResponse`.

Add conditional validation alongside the existing `custom_instruction` conditional-requirement
comment in `OutreachDraftRequest`'s docstring/description: `referral_context: str | None` field
(new, `max_length=500`), required when `strategy == "warm_referral"`, validated in the service
layer exactly like `custom_instruction`'s existing pattern (see
`backend/app/modules/outreach/service.py`'s `request_draft()`, lines 49-53) — add a sibling check
in the same method, not a new validator location.

## `backend/app/modules/outreach/models.py`

Add to `OutreachMessage`, directly after `message_type`:

```python
    strategy: Mapped[str] = mapped_column(
        String(20), default="direct_pitch", nullable=False, index=True
    )
    referral_context: Mapped[str | None] = mapped_column(Text, nullable=True)
```

## Migration

Migration number note: this is the **third** track in this planning doc set to want revision
number `047` (`machine-1-tenancy-core/02` and `machine-2/02-country-demand-intelligence` also
each write a `047_*` file). All three tracks are dispatched to run in parallel, so whichever
actually lands first in a real PR keeps `047`; the other two must be renumbered to whatever the
real head is at the time each is implemented. **Do not assume `047` is free — run
`python -m alembic heads` from `backend/` immediately before writing this migration file** and
use the real next number and real `down_revision`.

```python
"""Add outreach strategy dimension (strategy, referral_context) to outreach_messages.

Revision ID: 047_outreach_strategy_dimension
Revises: <real current head — verify before writing>
Create Date: 2026-08-22
"""

def upgrade() -> None:
    op.add_column(
        "outreach_messages",
        sa.Column("strategy", sa.String(20), nullable=False, server_default="direct_pitch"),
    )
    op.create_index("ix_outreach_messages_strategy", "outreach_messages", ["strategy"])
    op.add_column("outreach_messages", sa.Column("referral_context", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("outreach_messages", "referral_context")
    op.drop_index("ix_outreach_messages_strategy", table_name="outreach_messages")
    op.drop_column("outreach_messages", "strategy")
```

## `backend/app/modules/outreach/service.py` — `OutreachService.request_draft`

After the existing `custom_instruction` conditional check (lines ~49-53), add the mirrored check:

```python
        if body.strategy == "warm_referral" and not (body.referral_context or "").strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="referral_context is required when strategy='warm_referral'",
            )
```

Pass `body.strategy` and `body.referral_context` through the existing `queue.enqueue(...)` call
(lines 77-88) as two additional positional arguments to
`generate_outreach_draft_job` (see below) — append them after `body.custom_instruction`, and
update the Redis lock key (lines 66-69) to **not** include strategy (the lock's purpose is
preventing duplicate concurrent drafts for the same company/job/message-type; two different
strategies for the same company are still "duplicate work" in the sense this lock guards against,
so strategy is deliberately excluded from the lock key — document this reasoning inline if the
implementer's judgment differs).

## `backend/app/workers/tasks/outreach.py`

Add `strategy: str = "direct_pitch"` and `referral_context: str | None = None` parameters to both
`generate_outreach_draft_job` and `_generate_outreach_draft_job`, threaded through to
`_draft_with_llm` and stored on the new `OutreachMessage` row (lines 142-154).

In `_draft_with_llm`, add a strategy-specific instruction fragment, composed with the existing
`_SYSTEM_PROMPTS_BY_TYPE` selection rather than replacing it — strategy and channel are
orthogonal dimensions:

```python
_STRATEGY_INSTRUCTIONS = {
    "direct_pitch": "State your interest and relevant qualifications plainly and ask for a conversation.",
    "value_first": "Open by naming one specific, concrete way you could help this company (grounded in the job description or company context provided) before mentioning your own qualifications.",
    "curiosity": "Open with a genuine, specific question about the company or role that invites a reply, rather than opening with a pitch about yourself.",
    "warm_referral": "Reference the referral/connection context provided below naturally near the opening of the message.",
}
```

Append `_STRATEGY_INSTRUCTIONS.get(strategy, _STRATEGY_INSTRUCTIONS["direct_pitch"])` to
`user_content` (after the existing company-context line, before the `custom_instruction`
append), and append `referral_context` to `user_content` when `strategy == "warm_referral"`
(following the same append-pattern already used for `custom_instruction`, lines 268-269).

## Do not touch

- `backend/app/clients/perplexity.py` — company research is unaffected by strategy; do not
  change how company context is fetched.
- `backend/app/modules/job_matching/` — untouched.
- `backend/app/modules/admin/moderation_flagging.py` — `flag_if_needed`'s call site
  (lines 179-191 of `outreach.py`) is untouched; strategy-authored text still flows through the
  same `text_fields=[subject, body]` moderation check unchanged.
- Do not touch `OutreachEditRequest` — edited drafts keep whatever strategy they were drafted
  with; strategy is not editable post-draft in this chunk (a candidate/recruiter who wants a
  different strategy re-drafts, they don't mutate strategy on an existing draft — this mirrors
  how `message_type` itself is also not editable via `OutreachEditRequest` today).

## Verification

- Existing outreach tests (`backend/tests/` — locate the outreach test module(s) before
  assuming a path) must pass with `strategy` defaulting to `"direct_pitch"` for all existing
  test call sites that don't pass it explicitly (backward compatibility check).
- Add a test per strategy value asserting the correct `_STRATEGY_INSTRUCTIONS` fragment appears
  in the constructed `user_content` passed to the LLM call (mock the OpenAI call, assert on the
  payload, following the existing test pattern for `message_type`-specific system prompts, if one
  exists).
- Add a test asserting `request_draft()` 400s when `strategy="warm_referral"` and
  `referral_context` is empty/missing.

## Frontend

Searched the real `frontend/` tree for the existing outreach draft-request call site rather than
guessing a path. The confirmed component is
`frontend/features/outreach/components/DraftOutreachDialog.tsx` — a confirmation dialog shown
between clicking "Draft outreach" (in `SwipeDeckView.tsx`, `job-swipe`'s trigger point) and
enqueuing the draft-generation job. It currently renders a `messageType` `<Select>` (Email/
LinkedIn message/Generic message/Custom) and a conditional `customInstruction` `<Textarea>` when
`messageType === "custom"`, then calls `onConfirm({ messageType, customInstruction })`. The
mutation itself is wired through `frontend/features/outreach/hooks/useOutreach.ts`'s
`useDraftOutreachForMatch`/`useDraftOutreach`, which call `draftOutreach(payload)` from
`frontend/src/lib/api-client.ts`.

**Add a `strategy` field to this existing form — do not invent a new page.**

- Edit `DraftOutreachDialog.tsx`: add a second `<Select>` (or a `<RadioGroup>` if that's the
  existing convention for a 4-option choice elsewhere in this codebase — check
  `frontend/components/ui/` before picking one over the other) for `strategy`
  (`OutreachStrategy` — `direct_pitch`/`value_first`/`curiosity`/`warm_referral`), defaulting to
  `"direct_pitch"` to match the backend schema's default. Add a conditional `referral_context`
  `<Textarea>` shown when `strategy === "warm_referral"`, mirroring the existing
  `messageType === "custom"` → `customInstruction` conditional-field pattern already in this same
  file (same component, same conditional-rendering idiom, not a new pattern).
- Update `DraftOutreachDialogProps.onConfirm`'s payload type to include
  `strategy: OutreachStrategy` and `referralContext?: string`.
- Edit `frontend/features/outreach/hooks/useOutreach.ts`: add `strategy?: OutreachStrategy` and
  `referralContext?: string` to `useDraftOutreach`'s and `useDraftOutreachForMatch`'s
  `mutationFn` payload types, threaded through to `draftOutreach(payload)` — `draftOutreach`
  itself lives in `frontend/src/lib/api-client.ts`; add the two new fields to whatever request
  body type it sends, following its existing field-naming convention (camelCase in the TS payload,
  mapped to the backend's snake_case `strategy`/`referral_context` at the API-client boundary,
  matching how `customInstruction`/`custom_instruction` is already mapped there today).
- Edit `frontend/features/job-swipe/components/SwipeDeckView.tsx`'s `handleConfirmDraft`: thread
  the new `strategy`/`referralContext` fields from the dialog's `onConfirm` payload through to
  `draftOutreach.mutate(...)`'s call, mirroring exactly how `messageType`/`customInstruction` are
  already threaded through in that same function today.
- New type: add `OutreachStrategy` to `frontend/src/lib/types.ts` (mirroring the existing
  `OutreachMessageType` literal union already there), rather than duplicating the literal inline
  in each component file.
