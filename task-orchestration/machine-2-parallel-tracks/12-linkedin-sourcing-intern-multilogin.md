# Machine 2, Track 12 — LinkedIn Sourcing (Intern + Multilogin)

## ⚠️ Legal risk — read before implementing anything in this file (at least as prominent as `06`'s)

**This chunk's fact pattern is closer to the actual `hiQ Labs v. LinkedIn` judgment than `06`'s
(outbound sending) is.** The real case (Case No. 17-cv-03301-EMC, N.D. Cal.) ended in a **$500,000
consent judgment in December 2022**, and the claims that judgment actually rested on were
**data scraping and creation of fake LinkedIn accounts to evade detection/access limits** — not
"automated messaging" (see `06-linkedin-outreach-send.md`'s own corrected citation for that
distinction, and do not reintroduce the messaging-attribution error here). **Sourcing/scouting
candidate profile data from LinkedIn is exactly the scraping-adjacent activity that case actually
punished**, which makes this chunk's legal exposure at least as serious as `06`'s, arguably more
directly on-point.

This means:

- **No scripted/automated scraping of any kind.** No headless browser driving a LinkedIn search
  and extracting profile fields programmatically, no bulk export tooling, no API calls against
  LinkedIn's private/undocumented endpoints, no browser-extension-based bulk extraction. If an
  implementer or reviewer of this chunk finds themselves building anything that reads a LinkedIn
  page's DOM/response and writes structured fields into this platform's database *without a human
  manually typing/copying each value*, **stop and escalate to a human decision-maker before
  proceeding** — that decision is explicitly out of this chunk's authority to make unilaterally,
  identical to `06`'s own escalation instruction for "just automate the click too."
- **No fake-account creation of any kind.** The Multilogin profiles this chunk's design covers
  (see below) are for managing an intern's own *real*, individually-owned LinkedIn account
  sessions consistently (consistent fingerprint/proxy so a legitimate account doesn't get
  challenged/flagged by LinkedIn's own anti-bot systems for looking like a new device each
  session) — never for creating additional accounts to evade LinkedIn's per-account
  rate/visibility limits. One Multilogin profile per one real, intern-owned LinkedIn account,
  1:1, always.
- **The entire workflow this chunk specs is manual, human-driven data entry: an intern looks at a
  LinkedIn profile with their own eyes in their own logged-in session, and manually types/pastes
  what they observed into this platform's UI.** There is no code in this chunk that reads
  anything from linkedin.com programmatically. This is the single most important design
  constraint in this entire file.

This chunk still specs a "sourced-lead" data-entry surface and light Multilogin
profile/account-management bookkeeping, as required by the broader effort — but, exactly as `06`
already establishes for outbound sending, **the design below is deliberately manual, not a
scraper**, specifically to reduce (not eliminate — there is no zero-risk version of scouting a
third party's platform for recruiting leads) the legal exposure described above.

## Depends on

Nothing from `06-linkedin-outreach-send.md` structurally — this chunk is explicitly **distinct**
from `06`. `06` is about outbound message sending (task-queue for a human to click "send" on an
already-drafted message to a known target). This chunk is about sourcing/scouting: finding
candidate profiles in the first place, before any outreach message exists. Read `06` for the
"how prominent should the risk section be, and how does this repo phrase task-queue-not-automation
designs" convention, but do not import from or depend on `06`'s files (`linkedin_send_*`) — this
chunk has its own new module, entirely separate from `06`'s queue.

## Design: manual lead-entry form, not a browser/scraping integration

1. An intern opens their own Multilogin (anti-detect browser) profile — a browser profile
   isolated from every other profile's cookies/fingerprint/proxy, so their one real LinkedIn
   account behaves consistently session-to-session (see "Multilogin profile/account management"
   below).
2. The intern manually searches/browses LinkedIn inside that browser session, exactly as any
   human LinkedIn user would, looking for profiles matching target sourcing criteria (a role,
   seniority, location, etc. — communicated to the intern out-of-band, e.g. via a written brief;
   this chunk does not build a "search criteria" UI feature, since the intern is doing the actual
   searching on linkedin.com itself, in their own browser, with LinkedIn's own search UI).
3. When the intern finds a profile worth logging, they switch to this platform's own **new
   sourced-lead entry form** and manually type/paste what they observed: name, headline/current
   role, location, the profile URL, and free-text notes. **No field in this form is
   auto-populated from LinkedIn** — every field is typed by the intern from what they read on the
   screen, the same way a recruiter today might jot notes in a spreadsheet.
4. The submitted lead becomes a `SourcedCandidateLead` row, visible to recruiters as a queue of
   "leads an intern found," which a recruiter can later act on (e.g. reach out via the existing
   `06` LinkedIn-send task-queue design, using the `linkedin_profile_url` the intern logged —
   this chunk produces an *input* to `06`'s queue, it does not itself send anything).

## Files to create

- `backend/app/modules/linkedin_sourcing/__init__.py`
- `backend/app/modules/linkedin_sourcing/models.py`
- `backend/app/modules/linkedin_sourcing/schemas.py`
- `backend/app/modules/linkedin_sourcing/repository.py`
- `backend/app/modules/linkedin_sourcing/service.py`
- `backend/app/modules/linkedin_sourcing/router.py`
- `backend/alembic/versions/053_linkedin_sourced_leads.py` (verify real next number — fourth new
  chunk in this batch wanting a `05x` slot alongside `08`/`09`/`11`; re-run
  `python -m alembic heads` before writing `down_revision`)
- `frontend/app/app/admin/sourcing-leads/page.tsx` (intern data-entry + recruiter review UI,
  following the same sibling-admin-page convention `06`'s own
  `frontend/app/app/admin/linkedin-tasks/page.tsx` already uses, under the existing
  `frontend/app/app/admin/layout.tsx`)

## `backend/app/modules/linkedin_sourcing/models.py`

```python
"""Human-in-the-loop LinkedIn sourcing/scouting lead log. See this file's parent
directory's 12-linkedin-sourcing-intern-multilogin.md for why this is a manual
data-entry form filled out by a human who read a LinkedIn profile themselves, and
NEVER a scraper — that file's legal-risk section is the most important thing to
read before touching this module."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class SourcedCandidateLead(Base):
    __tablename__ = "sourced_candidate_leads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # The intern who manually observed and typed in this lead. Never NULL — every
    # row must be attributable to a specific human who actually looked at the
    # profile, both for accountability and because "who sourced this" is itself
    # useful recruiting-ops data.
    sourced_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    headline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    linkedin_profile_url: Mapped[str] = mapped_column(String(512), nullable=False)
    target_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="new", nullable=False, index=True
    )  # "new" | "reviewed" | "contacted" | "dismissed"
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
```

Note `sourced_by`'s `ForeignKey(..., ondelete="SET NULL")` paired with `nullable=True` at the
column level (a small inconsistency with the docstring's "never NULL" intent) — this follows the
exact same pattern `06`'s own `LinkedInSendTask.claimed_by` already uses (nullable column,
`SET NULL` on delete, so a deleted user's historical rows survive without a dangling FK) even
though the *application-level* invariant is "always set at creation time." Enforce "never NULL at
creation" in `service.py`'s create function, not at the column-nullability level, matching how
`06`'s own file handles the same tension for its `claimed_by`/`outcome_note` pattern.

## `backend/app/modules/linkedin_sourcing/schemas.py`

```python
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class CreateSourcedLeadRequest(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255)
    headline: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=255)
    linkedin_profile_url: str = Field(..., max_length=512)
    target_role: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


class SourcedLeadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    sourced_by: UUID | None
    full_name: str
    headline: str | None
    location: str | None
    linkedin_profile_url: str
    target_role: str | None
    notes: str | None
    status: str
    created_at: datetime


class ReviewSourcedLeadRequest(BaseModel):
    status: str = Field(..., pattern="^(reviewed|contacted|dismissed)$")
```

`linkedin_profile_url` is a plain validated string (max-length + basic format check in the
service layer, e.g. must start with `https://www.linkedin.com/`), not a strict `HttpUrl` type —
following the same "just enough validation, no over-engineering" convention `06`'s own
`linkedin_profile_url: Mapped[str] = mapped_column(String(512), ...)` already uses without a
stricter type.

## `backend/app/modules/linkedin_sourcing/service.py` — key functions

```python
async def create_lead(
    db: AsyncSession, *, sourced_by: UUID, body: CreateSourcedLeadRequest
) -> SourcedLeadResponse:
    """Simple insert — this is a data-entry form, not a workflow with side
    effects. No suppression check here (unlike 06's enqueue_send_task) since
    logging a lead is not itself contacting anyone; suppression is checked later,
    at whatever point a recruiter actually initiates outreach using this lead's
    linkedin_profile_url (06's existing enqueue_send_task already does this for
    LinkedIn sends — this chunk does not duplicate that check)."""
    ...


async def list_leads(db: AsyncSession, *, status: str | None = None) -> list[SourcedLeadResponse]:
    """Visible to any recruiter (not scoped to sourced_by — the whole point is a
    shared queue of leads for any recruiter to review, mirroring 08's shared-pool
    philosophy: sourcing an intern's lead does not make it 'that intern's lead'
    in an access-restrictive sense any more than assigning a candidate does)."""
    ...


async def review_lead(
    db: AsyncSession, *, lead_id: UUID, reviewer_id: UUID, body: ReviewSourcedLeadRequest
) -> SourcedLeadResponse: ...
```

## `backend/app/modules/linkedin_sourcing/router.py`

```
POST /api/linkedin-sourcing/leads          -> create_lead   (intern-facing entry form submit)
GET  /api/linkedin-sourcing/leads          -> list_leads    (recruiter review queue; optional
                                                              ?status= filter)
POST /api/linkedin-sourcing/leads/{id}/review -> review_lead (recruiter marks
                                                              reviewed/contacted/dismissed)
```

Gate behind a new permission `("linkedin_sourcing", "write")` for `create_lead`/`review_lead`
(seed via this chunk's migration, following `04-rbac-admin-platform.md`'s seeding pattern if it
has landed, else seed directly here without blocking on `04` — identical "do not block" note as
every other new chunk in this batch); `list_leads` requires authentication only (any
recruiter/staff can view the shared queue, per the "not access-restrictive" note in `service.py`
above).

## Multilogin profile/account management (at a level consistent with how `06` discusses infrastructure)

`06`'s own file explicitly notes the existing Tier-1 Multilogin infrastructure
(`backend/app/integrations/multilogin/profile_pool.py`) is **read-only today** (photo
enrichment) and instructs implementers not to import from it for sending. **This chunk follows
the identical instruction: do not import from or extend `app.integrations.multilogin.profile_pool`
for sourcing either.** The Multilogin usage this chunk describes is entirely an *operational*
practice for the human intern, not a code integration:

- **One Multilogin browser profile per one real, intern-owned LinkedIn account — always 1:1,
  never many-profiles-per-account or many-accounts-per-profile.** A profile is not a shared pool
  resource the way `profile_pool.py`'s existing Tier-1 rotation logic treats browser profiles for
  read-only enrichment; it is a dedicated, persistent identity for one intern's one account.
- **Consistent fingerprint and proxy per profile.** Multilogin's anti-detect browser preserves a
  stable canvas/WebGL/font/timezone fingerprint and a fixed (or narrowly-scoped, e.g. same city)
  proxy across sessions for a given profile, so the underlying LinkedIn account is not repeatedly
  presented as if logging in from a new device/location every session — which is itself a
  significant trigger for LinkedIn's own anti-bot/account-verification challenges, independent of
  any legal-risk consideration. This is standard operational hygiene for *any* legitimate,
  frequently-used account, not a technique for evading detection of the underlying human activity
  (the human activity — an intern manually browsing profiles — is not something LinkedIn's terms
  actually prohibit; consistent fingerprinting just avoids false-positive account-security
  friction for a real, individually-owned account used more heavily than a typical one).
- **No automated actions run inside a Multilogin profile by this chunk's code.** The profile is
  opened by the intern, used by the intern, and closed by the intern — there is no scheduled job,
  no Selenium/Playwright script, no API call that drives a Multilogin browser instance
  programmatically anywhere in this chunk. This is a deliberate, hard boundary (see the Legal
  risk section above).
- Recording *which* Multilogin profile an intern used for a given lead is out of scope for this
  chunk's own tables (`SourcedCandidateLead` has no `multilogin_profile_id` column) — profile
  assignment/tracking, if wanted, is an operational/HR bookkeeping concern outside this
  platform's database, not a feature this chunk needs to build to satisfy its stated goal
  (logging sourced leads). Do not add such a column speculatively.

## Ambiguities resolved

- **Why not let the intern paste a LinkedIn profile URL and have the platform fetch/prefill the
  name/headline/location automatically?** Explicitly rejected — fetching *any* field
  programmatically from a LinkedIn URL, even a single field, even server-side, is exactly the kind
  of automated data extraction the Legal risk section above flags as closest to the actual hiQ
  fact pattern. Every field in `CreateSourcedLeadRequest` must be manually typed by the intern
  from what they observed with their own eyes. This is a deliberate, non-negotiable constraint on
  this chunk's design, not an oversight to "optimize" later.
- **Should this chunk wire directly into `06`'s `LinkedInSendTask` queue (e.g.
  auto-create a send task the moment a lead is logged)?** No — sourcing and sending remain two
  separate, recruiter-gated steps. A recruiter reviewing the lead queue (`list_leads`) decides
  whether and how to act on a given lead (e.g. by separately using `06`'s existing outreach-draft
  ->  `06`'s send-task-queue flow with the lead's `linkedin_profile_url`); this chunk does not
  auto-create anything in `06`'s tables. Keeping these decoupled means a `SourcedCandidateLead`
  that never gets acted on has zero downstream effect, and a recruiter's decision to act is always
  an explicit, auditable step.
- **Does `sourced_by` need brand/org scoping?** No — per the shared-pool model (`08`'s "no
  access-control gate" philosophy applies here too): any recruiter can review any intern's
  sourced leads, since there is one shared candidate/lead pool, not per-brand-isolated lead
  queues.

## Do not touch

- `backend/app/integrations/multilogin/profile_pool.py`, `backend/app/integrations/linkedin/` —
  not imported, not modified, not extended. Same boundary `06` already draws for its own
  scope, restated here because this chunk is even more directly adjacent to Multilogin/LinkedIn
  infrastructure by subject matter and could tempt an implementer to "just reuse the existing
  pool" — do not.
- `backend/app/modules/outreach/linkedin_send_models.py`, `linkedin_send_service.py`,
  `linkedin_send_router.py` (all `06`'s files) — untouched; this chunk produces leads that a
  recruiter may later use as *input* to `06`'s existing flow, but does not call into or modify any
  of `06`'s code.
- Do not add any Selenium/Playwright/browser-automation dependency to `backend/pyproject.toml` (or
  equivalent) as part of this chunk — there is no automated browser driving anywhere in this
  design; adding such a dependency at all would be a signal something in the implementation has
  drifted from this chunk's manual-only design.
- Do not build a "bulk import leads from a CSV/spreadsheet export of a LinkedIn search results
  page" feature — that is a scraping-adjacent bulk-extraction shortcut in disguise (the CSV export
  itself would have to come from somewhere), explicitly out of scope; leads are logged one at a
  time, one manual form submission per profile a human actually reviewed.

## Verification

- Test: `create_lead` requires `sourced_by` to be set (service-layer check; a request without an
  authenticated caller identity cannot create a lead — there is no "anonymous/system-sourced"
  lead path).
- Test: `list_leads` returns leads created by different `sourced_by` users (confirms the shared,
  non-access-restrictive queue — mirroring `08`'s own access-control regression test pattern).
- Test: `review_lead` updates `status`/`reviewed_by`/`reviewed_at`; rejects an invalid `status`
  value outside the three allowed transitions (422, via the schema's `pattern` constraint).
- Test: `POST /api/linkedin-sourcing/leads` 403s for a caller lacking `linkedin_sourcing:write`.
- **Design-boundary check (release-blocking, code-review item not an automated test):** the
  reviewer of this chunk's PR must confirm no HTTP client call, browser-automation import, or any
  code path in the diff reads from or requests `linkedin.com` in any form — the entire feature
  surface should be a plain CRUD form over `SourcedCandidateLead`, with zero network calls to any
  third-party site. If the reviewer finds any such call, this is an automatic block, not a style
  comment — mirroring `06`'s own "no LinkedIn network call, browser automation, or credential
  usage" verification requirement, applied here to the sourcing side instead of the sending side.
