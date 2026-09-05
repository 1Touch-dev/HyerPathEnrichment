# Machine 2, Track 5 — Outreach CAN-SPAM Send Compliance

## Depends on

`03-outreach-strategy-dimension.md`'s `OutreachMessage.strategy`/`referral_context` columns
existing (same model file, same migration lineage — this chunk's migration must set
`down_revision` to `03`'s migration, not skip past it).

## Legal context (for the PR description, not necessarily a code comment)

CAN-SPAM has **no B2B exception** — a message to a hiring manager at a company is still covered.
Requirements relevant here: accurate From/Reply-To headers (no header spoofing), a
non-deceptive subject line, a valid physical postal address in the message, and a working
opt-out mechanism honored within 10 business days. Platform liability does not transfer to a
sending vendor merely because a candidate typed the message.

## Ground truth (verified 2026-08-22)

`OutreachService.send_message()` (`backend/app/modules/outreach/service.py`, lines 123-162)
does **not** transmit email over SMTP today — its own docstring states this explicitly ("no
email-sending infra targeting arbitrary third-party recipients exists in this repo today"). It
appends `_UNSUBSCRIBE_FOOTER_TEMPLATE` (lines 27-33) and marks the message `status="sent"`; the
candidate is expected to copy/send the text themselves. **There is also no `recipient_email`
field anywhere in `OutreachMessage`/`OutreachDraftRequest`/`OutreachEditRequest` today** — the
schema has `company_name` and `recipient_role_title` but never stores who the message is
actually addressed to. This chunk closes both gaps enough to make the CAN-SPAM requirements
*meaningful* (a real recipient address to check against suppression, a real postal address in
the footer) even though real SMTP transmission remains explicitly out of scope (unchanged from
today — this chunk hardens the compliance shape of the existing "draft + candidate sends it
themselves" flow, it does not build an SMTP sender).

Suppression already exists and is reusable as-is:
`app/compliance/suppression.py`'s `check_suppression(db, identifier)` /
`add_suppression(db, identifier, reason)` — Redis-set fast path (`SUPPRESSION_SET_KEY =
"suppression:hashes"`) with a SQL `SuppressionRecord` durable fallback (ADR 0005). The existing
`/api/opt-out` endpoint (`backend/app/modules/opt_out/router.py`) already lets any identifier
(including an email address) register there. This chunk **reuses this exact suppression store**
for outbound-outreach suppression — it does not create a parallel suppression table.

## Files to edit

- `backend/app/modules/outreach/schemas.py`
- `backend/app/modules/outreach/models.py`
- `backend/app/modules/outreach/service.py`
- `backend/app/modules/outreach/router.py`
- `backend/app/core/config.py`
- `backend/alembic/versions/048_outreach_recipient_and_canspam.py` (verify real next number)

## `backend/app/modules/outreach/schemas.py`

Add `recipient_email: str | None = Field(default=None, max_length=320)` to
`OutreachDraftRequest`. Validate in the service layer (same conditional-requirement pattern as
`custom_instruction`/`referral_context`): required when `message_type == "email"`, since CAN-SPAM
suppression and the physical-address footer only apply to actual email sends; not required for
`linkedin`/`generic`/`custom` types (LinkedIn's own send path is `06`'s job; `generic` messages
are informal contact-you-already-know notes per the existing `_GENERIC_SYSTEM_PROMPT`, not
covered by CAN-SPAM's commercial-email definition in the same way).

Add `recipient_email: str | None` to `OutreachMessageResponse`.

## `backend/app/modules/outreach/models.py`

Add to `OutreachMessage`:

```python
    recipient_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    # CAN-SPAM: set once at send time from the identifier-hash suppression check
    # (app/compliance/suppression.py), not editable after — a message that was
    # suppression-blocked stays blocked even if suppression state later changes,
    # so a recruiter can't "retry" past a real opt-out by re-sending the same draft.
    suppression_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

## `backend/app/core/config.py`

CAN-SPAM requires a physical postal address in the message. Add, following the existing string-
field convention:

```python
# CAN-SPAM (backend/app/modules/outreach/service.py's footer): the platform's registered
# postal address, included in every outbound email-type outreach message. Required by
# law, not cosmetic — leave unset only in environments where OUTREACH_ENABLED is also
# False. No default value: an empty address must not silently ship in a real send.
outreach_physical_address: str = Field(default="", alias="OUTREACH_PHYSICAL_ADDRESS")
```

Add a sibling startup validation, `validate_outreach_settings(settings: Settings | None = None) -> None`,
following the exact shape of the existing `validate_tier1_settings()`
(`backend/app/core/config.py`, lines 409-424+: no-op when the owning flag is off, raise
`RuntimeError` listing missing env key *names* only, never secret values):

```python
def validate_outreach_settings(settings: Settings | None = None) -> None:
    """Fail fast when outreach is enabled without a CAN-SPAM-required physical address.

    Raises RuntimeError naming the missing env key. No-op when outreach_enabled is False.
    """
    cfg = settings if settings is not None else get_settings()
    if not cfg.outreach_enabled:
        return
    if not cfg.outreach_physical_address.strip():
        raise RuntimeError("OUTREACH_PHYSICAL_ADDRESS is required when OUTREACH_ENABLED is true")
```

Wire the call site the same way `validate_tier1_settings()` is already wired (locate its actual
call site — likely `app/core/lifespan.py`'s startup sequence — and add this call next to it,
matching the existing pattern rather than inventing a new startup-hook mechanism).

## `backend/app/modules/outreach/service.py`

Update `_UNSUBSCRIBE_FOOTER_TEMPLATE` (lines 27-33) to include the physical address and a
correct Reply-To statement:

```python
_UNSUBSCRIBE_FOOTER_TEMPLATE = (
    "\n\n---\n"
    "You're receiving this message because {sender_name} applied to or expressed interest in "
    "opportunities at {company_name} and used HyrePath to draft this note. "
    "Reply to {sender_email} directly, or let us know if you'd prefer not to receive further outreach.\n"
    "{sender_name} — sent via HyrePath, {physical_address}"
    "\nPrivacy policy: {privacy_url}"
)
```

Update `send_message()` (lines 123-162):

1. Require `message.recipient_email` to be set (validated at draft-creation time per the schema
   change above, but re-check defensively here too — a message drafted before this chunk shipped
   may have `recipient_email = None`; if so, raise
   `HTTPException(422, "This draft predates recipient-email tracking; discard and redraft")`
   rather than silently sending without a checkable recipient).
2. **Before** marking `status="sent"`, call
   `await check_suppression(self.db, message.recipient_email)` (import from
   `app.compliance.suppression`). If suppressed, raise
   `HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This recipient has opted out of outreach and cannot be messaged")`
   — do **not** mark the message sent, do **not** append the footer, in this branch.
3. Set `message.suppression_checked_at = datetime.now(UTC)` when the check passes.
4. Pass `physical_address=self._settings.outreach_physical_address` into the footer's
   `.format(...)` call (alongside the existing `sender_name`/`company_name`/`sender_email`/
   `privacy_url` kwargs).

## `backend/app/modules/outreach/router.py`

No signature change required for `send_message`'s route — `OutreachService.send_message` already
has access to `message.recipient_email` via the loaded `OutreachMessage` row, so no new request
body field is needed on the send endpoint itself (only on the draft-creation request, per the
schema change above).

## Migration

```python
def upgrade() -> None:
    op.add_column("outreach_messages", sa.Column("recipient_email", sa.String(320), nullable=True))
    op.add_column(
        "outreach_messages",
        sa.Column("suppression_checked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outreach_messages", "suppression_checked_at")
    op.drop_column("outreach_messages", "recipient_email")
```

## Do not touch

- `app/compliance/suppression.py`, `app/compliance/models.py`, `app/modules/opt_out/` — reused
  read-only via `check_suppression`; no changes to the suppression store itself in this chunk.
- `backend/app/workers/tasks/outreach.py` — draft *generation* is unaffected; this chunk only
  changes draft *creation* validation (recipient_email required for email type) and the *send*
  path. If `recipient_email` needs to be threaded through `request_draft`'s enqueue call so it's
  stored on the `OutreachMessage` row created by the worker job, that is an allowed edit here
  (the row is created in `_generate_outreach_draft_job`, not `send_message` — trace the exact
  field-setting call site before deciding whether the edit belongs in `service.py`'s
  `request_draft` enqueue-argument list plus `outreach.py`'s job signature, or elsewhere) — but
  do not change any LLM-prompt/drafting logic in that file.
- Do not touch `06-linkedin-outreach-send.md`'s scope — LinkedIn sends are not email and are not
  subject to CAN-SPAM in the same way; this chunk's suppression/postal-address logic is
  email-specific.

## Verification

- Test: drafting an `email`-type message without `recipient_email` returns 400/422.
- Test: `send_message` on a suppressed `recipient_email` returns 403 and leaves
  `status="draft"` (not `"sent"`), and does not append the footer to `message.body`.
- Test: `send_message` on a non-suppressed recipient succeeds, sets
  `suppression_checked_at`, and the footer includes `outreach_physical_address`'s value.
- Test: app startup with `outreach_enabled=True` and `outreach_physical_address=""` raises/logs
  per whatever pattern step "Add a startup validation" above lands on.
