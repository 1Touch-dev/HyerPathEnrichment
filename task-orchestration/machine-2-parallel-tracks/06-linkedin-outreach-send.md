# Machine 2, Track 6 — LinkedIn Outreach Send

## ⚠️ Legal risk — read before implementing anything in this file

LinkedIn's User Agreement §8.2 prohibits automated messaging and automated connection requests.
`hiQ Labs v. LinkedIn` (N.D. Cal., Case No. 17-cv-03301-EMC) ended in a **$500,000 consent
judgment (Dec 2022)** — but that judgment rests on **data scraping and fake-account
creation/breach-of-contract claims**, not on automated messaging: hiQ operated fake LinkedIn
accounts to scrape public profile data at scale for its own analytics product, and the judgment
followed from that conduct, not from sending outbound messages/connection requests. As of 2026,
LinkedIn's enforcement posture is **vendor-level takedowns** (e.g. the HeyReach takedown) — for
automated *outreach* specifically, LinkedIn's practical enforcement to date has been via User
Agreement §8.2 contract enforcement/account and vendor takedowns rather than through litigation on
the hiQ fact pattern. LinkedIn goes after the tool/vendor enabling automated outreach, not only the
end account. The existing Tier-1 LinkedIn infrastructure in this repo
(`backend/app/integrations/multilogin/profile_pool.py`, `backend/app/integrations/linkedin/`) is
**read-only today** (photo enrichment, `ENABLE_TIER1`-gated) and has **never been used to send
anything**. Reusing it for automated sending is a materially different, materially riskier use of
the same session-rotation/cooldown infrastructure than what it does today — and notably, that
kind of profile-scraping-via-automated-session usage is *closer* to the actual hiQ fact pattern
(scraping via automated/fake accounts) than outbound sending is, which is precisely why
`12-linkedin-sourcing-intern-multilogin.md` (a separate, later chunk covering LinkedIn
sourcing/scouting) carries its own explicit legal-risk section rather than reusing this one.

This chunk still specs the send/DM action layer and the intern task-queue UI, as required by the
broader effort — **but the design below is deliberately human-in-the-loop, not a fully automated
bot**, specifically to reduce (not eliminate — there is no zero-risk version of this) the legal
exposure described above. Any implementer or reviewer who finds themselves tempted to "just
automate the click too" should stop and re-read this section, and escalate to a human decision-
maker before doing so — that decision is explicitly out of this chunk's authority to make
unilaterally.

## Depends on

`03-outreach-strategy-dimension.md` (reuses `OutreachStrategy`, `OutreachMessage.strategy`) and
`05-outreach-cansPAM-send-compliance.md` (reuses the suppression-check pattern, applied here to
LinkedIn profile URLs instead of email addresses).

## Design: task-queue, not auto-send

Instead of a bot that logs in and clicks "Send" on LinkedIn, this chunk builds:

1. A **drafting** path (reuses `03`'s strategy dimension + existing `message_type="linkedin"`
   drafting in `backend/app/workers/tasks/outreach.py`) — already exists, unchanged by this
   chunk.
2. A new **`LinkedInSendTask`** queue: once a LinkedIn-type `OutreachMessage` is approved for
   sending, it becomes a task in a human work queue instead of triggering an automated browser
   action. A human operator (an "intern" role, per the effort's naming) opens the task, which
   shows the drafted message and the target profile URL, and the operator performs the actual
   LinkedIn action **themselves, in their own logged-in LinkedIn session**, then marks the task
   done in the UI. This is the same category of workflow as "AI drafts, human sends" that
   `OutreachService.send_message()` already documents as the *existing* email behavior — this
   chunk extends that same shape to LinkedIn rather than inventing a new automated-sending path.
3. Existing Tier-1 Multilogin/LinkedIn browser infrastructure (`profile_pool.py`,
   `integrations/linkedin/`) is **not modified and not reused for sending** in this chunk. It
   stays exactly as it is today: read-only photo enrichment. Do not import from
   `app.integrations.linkedin.client` or `app.integrations.multilogin.profile_pool` anywhere in
   this chunk's new code.

## Files to create

- `backend/app/modules/outreach/linkedin_send_models.py`
- `backend/app/modules/outreach/linkedin_send_schemas.py`
- `backend/app/modules/outreach/linkedin_send_service.py`
- `backend/app/modules/outreach/linkedin_send_router.py`
- `backend/alembic/versions/049_linkedin_send_task_queue.py` (verify real next number —
  this is the fourth track in this doc set wanting a `047`-ish slot; by the time this chunk is
  implemented, `03`'s and `05`'s migrations should already be numbered, so re-run
  `python -m alembic heads` and pick up from there)
- `frontend/app/app/admin/linkedin-tasks/page.tsx` (intern task-queue UI — verified convention:
  sibling admin pages live at `frontend/app/app/admin/{feature}/page.tsx`, e.g.
  `frontend/app/app/admin/outreach/page.tsx`, `frontend/app/app/admin/roles/page.tsx`; a shared
  `frontend/app/app/admin/layout.tsx` already exists — this new page should sit under that same
  layout, not create a parallel one)

## `backend/app/modules/outreach/linkedin_send_models.py`

```python
"""Human-in-the-loop LinkedIn send task queue. See this file's parent directory's
06-linkedin-outreach-send.md for the legal-risk rationale for why this is a task
queue for a human operator, not an automated sender."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class LinkedInSendTask(Base):
    __tablename__ = "linkedin_send_tasks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    outreach_message_id: Mapped[UUID] = mapped_column(
        ForeignKey("outreach_messages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # The recipient's LinkedIn profile URL the operator should navigate to. Required —
    # unlike email, there is no other recipient identifier for this task type.
    linkedin_profile_url: Mapped[str] = mapped_column(String(512), nullable=False)
    action_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # "connection_request" | "inmail" | "direct_message"
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )  # "pending" | "claimed" | "completed" | "skipped"
    claimed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Operator's own note on outcome, e.g. "sent", "profile no longer exists", "already connected".
    outcome_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

**Future tenant-scoping note (definitive, not left open):** this table does not get its own
`org_id` column when tenancy retrofitting later reaches it
(`post-tenancy-retrofit/02-outreach-documents-portfolio-tenant-scoping.md`) — access control is
enforced transitively via a join to `outreach_message_id`'s parent `OutreachMessage.org_id`
instead. This chunk (`06`) does not need to do anything about this now (tenancy doesn't exist yet
when `06` is dispatched, per `00-overview.md`'s parallel-safety design) — it's noted here only so
a later implementer of the retrofit chunk doesn't have to rediscover this table's shape from
scratch, and so nobody is tempted to add a duplicate `org_id` column to this table later "just in
case." See that retrofit chunk's file for the full reasoning (the ownership-test rule and the
column-drift risk a join structurally avoids).

## `backend/app/modules/outreach/linkedin_send_service.py`

Key functions:

- `async def enqueue_send_task(db, *, outreach_message_id, linkedin_profile_url, action_type) -> LinkedInSendTask` —
  called from `OutreachService.send_message()` (see edit below) instead of that method's
  existing footer-append-and-mark-sent logic, **only when `message.message_type == "linkedin"`**.
- `async def claim_task(db, *, task_id, operator_id) -> LinkedInSendTask` — sets `status="claimed"`,
  `claimed_by`, `claimed_at`; 409s if already claimed by someone else.
- `async def complete_task(db, *, task_id, operator_id, outcome_note) -> LinkedInSendTask` — sets
  `status="completed"`, `completed_at`; **also** updates the parent `OutreachMessage.status` to
  `"sent"` and `sent_at` (only at this point — a LinkedIn-type message is not "sent" merely
  because a task was created, only when a human operator confirms they performed the action).
- `async def skip_task(db, *, task_id, operator_id, outcome_note) -> LinkedInSendTask` — sets
  `status="skipped"`; parent `OutreachMessage.status` stays `"draft"` (not sent, not failed —
  the candidate can re-request a draft or try a different approach).

Before enqueuing, reuse the suppression pattern from `05` conceptually (not the exact function,
since suppression is keyed on hashed identifiers and a LinkedIn profile URL is a valid identifier
for `hash_identifier`/`check_suppression` — reuse `app.compliance.suppression.check_suppression`
directly, called with `linkedin_profile_url` as the identifier): if the profile URL is suppressed
(a candidate previously opted out under that identifier), raise 403 and do not enqueue.

## `backend/app/modules/outreach/service.py` edit

In `send_message()` (lines 123-162 as of `05`'s changes), branch on `message.message_type`:

```python
        if message.message_type == "linkedin":
            await linkedin_send_service.enqueue_send_task(
                self.db,
                outreach_message_id=message.id,
                linkedin_profile_url=await self._resolve_linkedin_profile_url(message),
                action_type="connection_request" if message.strategy == "warm_referral" else "direct_message",
            )
            return self._to_response(message)  # status stays "draft" until a human completes the task
```

before the existing footer/mark-sent logic, which remains the path for `email` (and, per this
repo's existing behavior, `generic`/`custom`) message types. `_resolve_linkedin_profile_url` is a
new small helper — this chunk does not currently have a stored LinkedIn profile URL on
`OutreachMessage` (only `company_name`/`recipient_role_title`); add a `recipient_linkedin_url:
str | None` column to `OutreachMessage` in this chunk's migration, required at draft-creation
time when `message_type == "linkedin"` (same conditional-requirement pattern as `05`'s
`recipient_email`).

## Intern task-queue UI

`GET /api/outreach/linkedin-tasks` (new router) lists `pending`/`claimed` tasks for the
authenticated operator to work through; `POST /api/outreach/linkedin-tasks/{id}/claim`,
`.../complete`, `.../skip` map to the service functions above. Gate all of these behind a new
permission `("linkedin_tasks", "operate")` (seed it via this chunk's migration, following
`04-rbac-admin-platform.md`'s seeding pattern if that track has already landed — if not yet
landed, seed the permission row directly here without depending on `04`'s new CRUD endpoints;
either way, do not block on `04`).

Frontend: a simple table/list page showing pending tasks (drafted message text, target profile
URL as a plain link the operator clicks to open LinkedIn themselves, action type), with
Claim/Complete/Skip buttons. No embedded LinkedIn iframe, no in-app browser automation trigger —
the operator leaves the app to actually perform the LinkedIn action in their own browser/session,
by design (see the risk note at the top of this file).

## Do not touch

- `backend/app/integrations/linkedin/`, `backend/app/integrations/multilogin/` — not imported,
  not modified. This is the most important boundary in this chunk.
- `backend/app/core/config.py`'s `ENABLE_TIER1`/`browser_mode`/`multilogin_*` settings — unrelated
  to this chunk; do not add any LinkedIn-*credentials* settings here (there is no bot login in
  this design).
- `05-outreach-cansPAM-send-compliance.md`'s email-specific `recipient_email`/
  `outreach_physical_address` logic — untouched; this chunk only adds the LinkedIn-specific
  parallel fields/flow.

## Verification

- Test: `send_message` on a `linkedin`-type draft creates a `LinkedInSendTask` row and leaves
  `OutreachMessage.status == "draft"`.
- Test: `complete_task` transitions the parent message to `"sent"`; `skip_task` does not.
- Test: `enqueue_send_task` 403s when `linkedin_profile_url` is suppressed.
- Test: claiming an already-claimed task by a different operator 409s.
- No test in this chunk should assert or exercise any actual LinkedIn network call, browser
  automation, or credential usage — there is none in this design.
