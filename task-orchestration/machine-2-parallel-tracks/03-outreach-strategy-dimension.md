# Machine 2, Track 3 — Outreach Strategy Dimension

## Goal

Add a **strategy** dimension to outreach drafting — independent of `message_type` (channel:
email/linkedin/generic/custom) — so a recruiter can choose the *approach* a draft takes (e.g.
lead with a concrete value proposition vs. lead with curiosity vs. reference a warm referral)
without that becoming a fifth `message_type`. This chunk is a dependency for `05` (CAN-SPAM
compliance) and `06` (LinkedIn send) — both reuse the `OutreachMessage.strategy` column and the
`OutreachStrategy` literal type this chunk defines.

**Also adds two further, independent dimensions to the same drafting flow:**

1. A **manual, human-set company-tier field** on the target employer (e.g. `"premium"` vs.
   `"outsourcing"`) — see "Company tier (manual, target-employer-level)" below. This is
   deliberately **not** auto-computed by any enrichment/scraping job; a recruiter sets it based on
   their own judgment of the employer, and it persists across future drafts for the same employer.
2. **Role-type-driven strategy variation** — the outreach *approach* also varies by the role's
   type (technical vs. non-technical) and seniority (senior vs. junior), independent of the
   `strategy`/`message_type` dimensions already described above. See "Role-type-driven strategy
   variation" below.

## Files to edit

- `backend/app/modules/outreach/models.py`
- `backend/app/modules/outreach/schemas.py`
- `backend/app/modules/outreach/service.py`
- `backend/app/modules/outreach/repository.py` (new functions for company-tier lookup/upsert —
  check whether this file exists today; if outreach has no `repository.py` and DB access lives
  directly in `service.py`, add the new functions there instead and skip this file. **Ground
  truth, verified 2026-08-24: this file does exist today**, with `get_owned_message`/
  `list_messages_for_user`/`mark_sent` already in it — see the "Company-tier-driven drafting
  variation" section below for the new `get_company_tier` function this chunk adds to it.)
- `backend/app/modules/outreach/router.py` (new manual company-tier-setting endpoint — verify
  exact router filename/module; `outreach`'s router may be named differently, e.g. the existing
  draft/send endpoints could live in `service.py`'s own router or a dedicated `router.py`, check
  before assuming)
- `backend/app/workers/tasks/outreach.py`
- `backend/app/core/config.py` (new `enable_company_tier_in_outreach_drafting` flag — see
  "Company-tier-driven drafting variation" below)
- `backend/alembic/versions/047_outreach_strategy_dimension.py` (new file — see migration-number
  note below)

## Files to create

- None beyond what's listed above — the manual company-tier lookup is a new table added via the
  same migration as the `strategy`/`referral_context` columns (see "Company tier" section below),
  not a new module.

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

### Company tier (manual, target-employer-level)

`OutreachMessage` today has a free-text `company_name` (line 28) with no notion of a persistent
per-employer classification — every draft re-derives company context from scratch via
`perplexity.py`. Add a small new table, `EmployerCompanyTier`, that lets a recruiter manually
record a tier judgment per employer that persists across every future draft for that same
company, rather than re-asking the question per-draft:

```python
class EmployerCompanyTier(Base):
    """A recruiter's manual, human-set classification of a target employer. This is
    NOT auto-computed from any enrichment/scraping signal — it reflects a recruiter's
    own judgment call (e.g. a well-known, high-paying "premium" employer vs. a
    lower-paying staffing/outsourcing shop), and is set/edited explicitly through the
    admin UI, not derived by any background job."""

    __tablename__ = "employer_company_tiers"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # Matches OutreachMessage.company_name's free-text convention — no FK to a
    # dedicated "Company" table, because none exists today (company identity here is
    # a name string, same as everywhere else in this module).
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False)  # "premium" | "outsourcing"
    set_by_user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
```

`company_name` matching is exact-string, same normalization risk `OutreachMessage.company_name`
already carries elsewhere in this module (e.g. "Acme Inc." vs. "Acme, Inc" would be treated as two
different employers) — this chunk does not add company-name normalization/fuzzy-matching, since
no other part of this module has it either; flag it as a pre-existing, shared gap rather than
solving it only for this new table.

Read (`get_company_tier(db, company_name) -> EmployerCompanyTier | None`) and
upsert (`set_company_tier(db, *, company_name, tier, set_by_user_id, notes) -> EmployerCompanyTier`)
functions live in `repository.py`/`service.py` per the "Files to edit" note above, following
whichever of those two files already owns direct DB access for this module's other functions.

## Migration

Migration number note: this is the **third** track in this planning doc set to want revision
number `047` (`machine-1-tenancy-core/02` and `machine-2/02-country-demand-intelligence` also
each write a `047_*` file). All three tracks are dispatched to run in parallel, so whichever
actually lands first in a real PR keeps `047`; the other two must be renumbered to whatever the
real head is at the time each is implemented. **Do not assume `047` is free — run
`python -m alembic heads` from `backend/` immediately before writing this migration file** and
use the real next number and real `down_revision`.

```python
"""Add outreach strategy dimension (strategy, referral_context) to outreach_messages,
and the employer_company_tiers table for manual company-tier classification.

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

    op.create_table(
        "employer_company_tiers",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("set_by_user_id", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["set_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_name"),
    )
    op.create_index(
        "ix_employer_company_tiers_company_name", "employer_company_tiers", ["company_name"]
    )


def downgrade() -> None:
    op.drop_index("ix_employer_company_tiers_company_name", table_name="employer_company_tiers")
    op.drop_table("employer_company_tiers")

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

### Company-tier endpoint

Add a small manual-set endpoint to whichever router file owns this module's other outreach
endpoints (see "Files to edit" note above — verify the exact file/router name before adding):

```python
@router.put("/company-tier", response_model=CompanyTierResponse)
async def set_company_tier(
    body: SetCompanyTierRequest,  # company_name: str, tier: Literal["premium", "outsourcing"], notes: str | None
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> CompanyTierResponse: ...

@router.get("/company-tier", response_model=CompanyTierResponse | None)
async def get_company_tier(
    company_name: str,
    user: VerifiedUser,
    db: AsyncSession = Depends(get_db_session),
) -> CompanyTierResponse | None: ...
```

`set_company_tier` upserts by `company_name` (a recruiter re-setting an existing employer's tier
overwrites the previous value and `set_by_user_id`/`updated_at`, it does not create a duplicate
row — `company_name`'s `unique=True` constraint on `EmployerCompanyTier` enforces this at the DB
level too). No permission beyond the existing gate protecting other outreach endpoints in this
same router is required — this is not more sensitive than the drafting endpoints it sits beside.

`request_draft()` looks up the company tier and threads it into the LLM drafting prompt — see
"Company-tier-driven drafting variation" below for the concrete wiring (this supersedes an earlier
draft of this chunk that deferred this wiring as a follow-up; it is now in scope).

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

### Role-type-driven strategy variation

Outreach approach should also vary by the target role's type and seniority — a message to a
senior technical hiring manager reads differently than one to a junior non-technical recruiting
coordinator, independent of which `strategy`/`message_type` is selected. Add two new optional
fields to `OutreachDraftRequest` (`schemas.py`):

```python
OutreachRoleType = Literal["technical", "non_technical"]
OutreachSeniority = Literal["junior", "senior"]
```

```python
    role_type: OutreachRoleType | None = None
    seniority: OutreachSeniority | None = None
```

Both default to `None` (no adjustment — current behavior is preserved for every existing caller
that doesn't pass them, same backward-compatibility requirement as `strategy`'s own default).
These are recruiter-supplied on the draft request, mirroring how `strategy` itself is
recruiter-selected rather than auto-classified from `recipient_role_title` — this chunk does not
build a role-title classifier; a recruiter drafting outreach already knows whether the role is
technical/non-technical and senior/junior from the job posting they're working from.

Thread both through `generate_outreach_draft_job`/`_generate_outreach_draft_job` the same way
`strategy`/`referral_context` are threaded (additional optional parameters, stored on the new
`OutreachMessage` columns below), and add a second instruction-fragment dict in
`_draft_with_llm`, composed alongside (not replacing) `_STRATEGY_INSTRUCTIONS`:

```python
_ROLE_TYPE_INSTRUCTIONS = {
    ("technical", "senior"): "Speak with technical specificity and treat the recipient as a peer who can evaluate technical depth directly; keep it concise and skip generic enthusiasm.",
    ("technical", "junior"): "Keep technical references accessible; a junior technical hiring contact may be screening on behalf of others rather than evaluating deep technical fit themselves.",
    ("non_technical", "senior"): "Lead with business impact and outcomes rather than technical detail; a senior non-technical contact evaluates fit/communication/culture signals more than technical depth.",
    ("non_technical", "junior"): "Keep the message simple, warm, and outcome-focused; avoid jargon a junior non-technical screener may not be positioned to evaluate.",
}
```

Append `_ROLE_TYPE_INSTRUCTIONS.get((role_type, seniority))` to `user_content` when **both**
`role_type` and `seniority` are set (partial combinations — one set, one `None` — do not produce a
fragment; a recruiter who wants this adjustment must supply both dimensions, since the four
guidance strings above are only meaningfully defined pairwise). Place this append after the
strategy-instruction append and before the `custom_instruction`/`referral_context` appends,
matching the same ordering convention already used above (contextual/dimensional instructions
before candidate-specific free-text instructions).

Add matching columns to `OutreachMessage` (same migration as `strategy`/`referral_context` and
`employer_company_tiers` above):

```python
    role_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    seniority: Mapped[str | None] = mapped_column(String(20), nullable=True)
```

(Add the corresponding `op.add_column` calls to this chunk's migration's `upgrade()`/matching
`op.drop_column` calls to `downgrade()`, alongside the `strategy`/`referral_context` columns
already specified there.)

### Company-tier-driven drafting variation (wiring `EmployerCompanyTier` into the LLM prompt)

**Precedent for tiered outbound treatment.** Tier-driving-messaging is well-established outbound
practice, not a novel idea this chunk is inventing from nothing: HubSpot ships this natively as
an "ICP Tier" contact/company property that drives different playbooks per tier
(https://knowledge.hubspot.com/branding/get-started-with-account-based-marketing-in-hubspot), and
Salesforce Trailhead's own prospecting curriculum teaches the identical three-tier
(Tier 1/2/3) account-segmentation model for exactly this purpose
(https://trailhead.salesforce.com/content/learn/modules/prospecting-contact-strategy/plan-approach).
Outreach.io's own blog goes further and documents a "persona matrix" that maps distinct outbound
sequences to distinct segments, and is explicit that this tiering/persona assignment is **manually
set, not auto-scored**
(https://www.outreach.io/resources/blog/timeless-tips-for-sales-sequences) — a direct precedent
for this repo's own `EmployerCompanyTier` being a manual, recruiter-set field rather than an
enrichment/scraping output (see "Company tier (manual, target-employer-level)" above).

**Concrete wiring.** Add a third instruction dict in `backend/app/workers/tasks/outreach.py`,
sibling to `_STRATEGY_INSTRUCTIONS` and `_ROLE_TYPE_INSTRUCTIONS` above:

```python
_COMPANY_TIER_INSTRUCTIONS = {
    "premium": "This is a well-known, high-profile employer the candidate is likely already "
    "familiar with. Skip generic company introductions or explaining what the company does — "
    "assume the reader already knows their own employer's reputation. Lead with a sharp, specific "
    "value proposition and keep the tone confident and concise; avoid sounding star-struck or "
    "overly deferential toward a 'prestigious' employer.",
    "outsourcing": "This is a staffing/outsourcing employer, where the hiring contact may field "
    "many generic, low-effort candidate messages. Make genuine interest explicit and warm rather "
    "than assumed — name a specific reason this particular role/company is a fit, rather than a "
    "tone that could be mistaken for a mass-sent template.",
}
```

Add `get_company_tier(db: AsyncSession, company_name: str) -> EmployerCompanyTier | None` to
`backend/app/modules/outreach/repository.py` (this file already exists today — confirmed
2026-08-24, alongside `get_owned_message`/`list_messages_for_user`/`mark_sent` — so this is a new
function in an existing file, not a new module):

```python
async def get_company_tier(db: AsyncSession, company_name: str) -> EmployerCompanyTier | None:
    result = await db.execute(
        select(EmployerCompanyTier).where(EmployerCompanyTier.company_name == company_name)
    )
    return result.scalar_one_or_none()
```

In `_generate_outreach_draft_job` (`backend/app/workers/tasks/outreach.py`), look up the tier
alongside the existing Perplexity company-context lookup (same call site that already awaits
`perplexity.get_company_context(company_name, role_title)`) and thread the resulting `tier: str |
None` into `_draft_with_llm` as a new parameter, exactly the same way `strategy`/`role_type`/
`seniority` are already threaded through per the sections above. In `_draft_with_llm`, append
`_COMPANY_TIER_INSTRUCTIONS.get(tier)` to `user_content` (`None`/unset tier appends nothing —
`.get(tier)` returns `None` for a company with no `EmployerCompanyTier` row, and the existing
`if demand_line:`-style guard pattern already used elsewhere in this file applies here too: only
append when the lookup returns a non-`None` fragment).

**Append order is strategy → role-type → company-tier → custom_instruction/referral_context.**
This keeps this chunk's existing convention that a candidate's own free-text instruction has the
"last word" positionally in the prompt (see the ordering note already given for
`_ROLE_TYPE_INSTRUCTIONS` above) — company-tier is contextual/dimensional, same category as
strategy and role-type, so it slots in with them, before the candidate-specific free-text append.

**Flag-gated, not always-on.** Unlike `strategy`/`role_type`/`seniority` (which ship unconditional
in this chunk, since a recruiter must explicitly opt into each of them per-draft), wiring
`EmployerCompanyTier` into the prompt is gated behind a new config flag, added to
`backend/app/core/config.py` following the exact bool-flag convention already used by
`enable_tier1`/`outreach_enabled`:

```python
# Company-tier-driven outreach drafting (machine-2/03): append a tier-specific
# tone instruction (see _COMPANY_TIER_INSTRUCTIONS) to the drafting prompt when
# the target employer has a manually-set EmployerCompanyTier row. Default False:
# unlike strategy/role_type/seniority (recruiter-opted-in per draft, shipped
# unconditionally), this is an always-on-once-enabled behavior change for every
# draft to a tiered employer, and the tier->prompt-fragment mechanism itself has
# no published precedent (see this file's "Ambiguities resolved" section) — ship
# it off, human-review a small batch of real drafts, then enable broadly.
enable_company_tier_in_outreach_drafting: bool = Field(
    default=False, alias="ENABLE_COMPANY_TIER_IN_OUTREACH_DRAFTING"
)
```

so this specific mechanism can be reviewed against a small batch of real drafts before enabling it
broadly — see "Ambiguities resolved" below for why.

**Regression safety.** When no `EmployerCompanyTier` row exists for a given `company_name` (the
default state for every employer today, since this table is new), `get_company_tier` returns
`None`, `_COMPANY_TIER_INSTRUCTIONS.get(None)` returns `None`, and nothing is appended to
`user_content` — behavior for every existing caller/test must be byte-identical to pre-this-
section behavior. This is an explicit release-blocking verification item below, not just an
implied property.

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
- Do not build a role-title-to-`role_type`/`seniority` classifier — both fields are
  recruiter-supplied only in this chunk (see "Role-type-driven strategy variation" above).
- Do not build any automated reply-tracking/tone-drift-detection system for the company-tier
  wiring — see "Ambiguities resolved" below for why a human-review process substitutes for that
  here.

## Ambiguities resolved

- **Is "tier → different messaging tone" itself a proven pattern, or is this chunk inventing
  it?** The *general* practice of tiering driving different outbound content/tone is
  well-documented industry precedent (HubSpot's ICP Tier property, Salesforce's three-tier
  prospecting curriculum, Outreach.io's persona-matrix blog post, all cited above). **The
  specific mechanism this chunk uses — a tier value selecting a fragment appended directly into
  an LLM system/user prompt — has no published precedent anywhere in the sources above.** None of
  HubSpot, Salesforce, or Outreach.io describe LLM-prompt-fragment selection by tier; they
  describe tier selecting a *sequence*/*playbook*/*persona template*, a materially different
  (non-generative, deterministic) mechanism. This chunk's LLM-prompt-fragment approach is this
  repo's own reasonable extension of a proven idea into an LLM-drafting context, not itself a
  proven pattern — hence the flag-gate (`enable_company_tier_in_outreach_drafting`, default
  `False`) and the explicit requirement below to human-review a small batch of real drafts before
  enabling it broadly, rather than shipping it always-on the way `strategy`/`role_type` are.
- **What is the safety net for tone drift once enabled?** This repo has no automated
  reply-tracking or A/B-testing infrastructure for outreach today (no open/reply-rate metrics
  exist anywhere in `backend/app/modules/outreach/`), so an automated "did this tier fragment
  help or hurt" signal is not available. Outreach.io's own documented practice — clone a sequence
  step, split-test a variant, have a human review results before scaling the change — is the
  precedent this chunk borrows as its **recommended safety net**: before flipping
  `enable_company_tier_in_outreach_drafting` on for all recruiters, a human (the implementing
  team or a recruiter lead) should read through a small batch (e.g. 10-20) of real drafts
  generated with the flag on for both `"premium"` and `"outsourcing"` tiers, confirm the tone
  reads as intended and not as a strange/off-putting insertion, and only then enable it broadly.
  This is a process recommendation for the rollout, not new code — there is no ticket to build an
  A/B-testing harness in this chunk.

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
- Add a test per `(role_type, seniority)` pair asserting the correct `_ROLE_TYPE_INSTRUCTIONS`
  fragment appears in `user_content`; add a test asserting no role-type fragment is appended when
  only one of `role_type`/`seniority` is set (partial combination — see the explicit rule above).
- Add tests for the company-tier endpoint(s): setting a new tier creates a row; re-setting an
  existing employer's tier updates it in place rather than creating a duplicate (exercises the
  `company_name` unique constraint's upsert semantics); getting an unset employer's tier returns
  `None`/404 (whichever the response-model annotation above implies — pick one and be consistent).
- **Regression test (required, byte-identical check):** with `enable_company_tier_in_outreach_
  drafting` off (the default) and/or no `EmployerCompanyTier` row for the target `company_name`
  (the default state for every employer today), assert the constructed `user_content` is
  byte-identical to what it would have been before the "Company-tier-driven drafting variation"
  section's changes — this chunk's tier-wiring must be a strict no-op for every existing
  caller/test, exactly the same regression bar `07-demand-intelligence-resume-integration.md`
  holds itself to for its own flag.
- Add a test per tier value (`"premium"`, `"outsourcing"`) asserting the correct
  `_COMPANY_TIER_INSTRUCTIONS` fragment appears in `user_content` when the flag is on and a
  matching `EmployerCompanyTier` row exists.
- Add a test asserting `get_company_tier` performs no query difference based on the flag itself
  (the flag gates whether the *result* is used in the prompt, not whether the lookup runs) —
  document this explicitly if the implementer's judgment instead gates the lookup itself behind
  the flag too (either is defensible; be consistent and explicit about which was chosen).

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

**Add `role_type`/`seniority` selects to the same dialog.** Following the exact same pattern as
`strategy` above:

- Add two more `<Select>`s to `DraftOutreachDialog.tsx` for `roleType`
  (`OutreachRoleType` — `technical`/`non_technical`) and `seniority` (`OutreachSeniority` —
  `junior`/`senior`), both optional/unselected by default (matching the backend's `None` default —
  no adjustment unless the recruiter explicitly picks both).
- Thread `roleType`/`seniority` through `onConfirm`'s payload, `useDraftOutreach`/
  `useDraftOutreachForMatch`'s `mutationFn` payload types, and `SwipeDeckView.tsx`'s
  `handleConfirmDraft`, the same way `strategy`/`referralContext` are threaded above.
- Add `OutreachRoleType`/`OutreachSeniority` to `frontend/src/lib/types.ts`, alongside
  `OutreachStrategy`.

**Company tier: a small addition to the existing employer-facing outreach UI, not a new page.**
Add a "Company tier" control wherever the outreach UI already surfaces a target company by name
(e.g. alongside the company name shown on `SwipeDeckView.tsx`'s card, or on
`DraftOutreachDialog.tsx` itself — pick whichever existing surface already renders `company_name`
most prominently for a recruiter about to draft outreach, rather than adding a wholly new screen):
a `<Select>` (`"premium"` / `"outsourcing"` / unset) calling this chunk's new
`GET`/`PUT /api/outreach/company-tier` endpoints via two new client functions in
`frontend/src/lib/api-client.ts` (or wherever `draftOutreach` itself lives — same file), wired
through a small `useCompanyTier(companyName)`/`useSetCompanyTier()` pair of hooks in
`useOutreach.ts` following that file's existing React Query conventions.
