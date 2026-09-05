# Post-Tenancy Features, Chunk 6 — MCP Job Board Research (Idea List Only)

## ⚠️ Needs a dedicated research pass before any implementation scoping

**This file's job is to record James's idea and flag the research need it creates — not to spec
a build.** Unlike `04-upsell-and-side-tools-initiative.md` and
`05-freelance-bidding-system.md`, this idea is not blocked on the Abhishek/multiagentic-system
conversation (James's answer did not mention that dependency for this idea specifically) — it is
blocked on a concrete, answerable research question that has not yet been answered: **what MCP
(Model Context Protocol) servers already exist, if any, for major job-search/application
providers and ATSs, per region.** Grouped alongside `04`/`05` under `README.md`'s "Side
initiatives" heading anyway, since it is equally a separate, non-core-platform track — but for a
different reason (pending research, not pending an internal stakeholder conversation).

## Depends on

- A dedicated research pass (not yet done, as of 2026-08-25) into existing MCP server
  availability for major job boards/ATSs — see "Research question" below. Nothing in
  `machine-1-tenancy-core/` or `machine-2-parallel-tracks/` depends on this file, and this file
  depends on nothing else in this doc set.

## The idea (recorded, not scoped)

James's idea: use MCP integrations to connect this platform to major job-search/application
providers **per region**, so recruiters/agents aren't stuck building and maintaining bespoke
scrapers per job board (e.g. one-off scraping code per site, as this repo's existing
`backend/app/enrichers/jobspy.py` JobSpy/JSearch integration already does for a fixed set of
sources — `machine-2-parallel-tracks/02-country-demand-intelligence.md`'s "Ground truth" section
documents that existing plumbing). The appeal of MCP here is standardization: if a job board or
ATS already exposes (or a third party already maintains) an MCP server for it, integrating via
that protocol could mean less bespoke per-site scraping/parsing code to write and maintain as this
platform expands to more regions and more job sources — an explicit *reduction* of the kind of
per-source scraper proliferation this doc set's own LinkedIn-adjacent chunks
(`06-linkedin-outreach-send.md`, `12-linkedin-sourcing-intern-multilogin.md`) are otherwise
careful to avoid building automated scrapers for at all.

## Research question (must be answered before any implementation scoping)

**What MCP servers already exist for major job-search/application providers and ATSs, broken
down by region, and what do they actually expose (read job postings? submit applications?
candidate search? something else)?** This is not a rhetorical framing — it is the literal first
step anyone picking this idea up needs to take, and this file explicitly does not attempt to
answer it, since doing so would require actual research (checking MCP server registries/
directories, vendor documentation, and community projects as they exist at implementation time,
not guessing from this doc's authoring date) rather than being written into a planning document
speculatively. Concretely, before any chunk spec is written for this idea, someone needs to
answer, at minimum:

- Which major job boards (e.g. Indeed, LinkedIn Jobs, Glassdoor, government/regional job portals)
  and which major ATS platforms (e.g. Greenhouse, Lever, Workday) have a known MCP server today,
  official or community-maintained?
- For each one found: does it expose job-posting search/read access, application submission,
  candidate/profile data, or some combination — and under what auth/rate-limit/ToS terms?
- Does availability vary meaningfully by region (James's own framing implies it might — a US-
  focused job board's MCP coverage, if any, may not extend to non-US markets this platform also
  targets, per `02-country-demand-intelligence.md`'s Tier 1/2/3 market coverage)?
- For any provider with **no** existing MCP server, is one buildable without hitting the same
  scraping-adjacent legal exposure this doc set's LinkedIn chunks analyze in detail (`hiQ Labs v.
  LinkedIn`), or does "no existing MCP server" for a given source effectively mean "not currently
  a good candidate for this approach" for that source specifically?

## Ambiguities resolved

- **Should this file attempt to name specific MCP servers or vendors as already-confirmed
  options?** No — deliberately not done here. Naming specific vendors/servers without having
  actually done the research pass above would risk this planning doc set stating something as
  fact that is really a guess, which is exactly the kind of thing this task's instructions warn
  against doing for genuinely open items.
- **Should this idea be scoped as a replacement for the existing JobSpy/JSearch integration
  (`backend/app/enrichers/jobspy.py`)?** Not decided here — that is a real design question (does
  MCP integration for a given source replace, supplement, or run alongside the existing
  scraper-based integration for that same source) that depends entirely on what the research pass
  above finds; this file does not presume an answer.

## Do not touch

- Do not create any new backend module, migration, schema, or router for this idea as part of
  this chunk — this file's only deliverable is itself (the recorded idea plus the flagged
  research need).
- Do not modify `backend/app/enrichers/jobspy.py` or
  `machine-2-parallel-tracks/02-country-demand-intelligence.md`'s existing scope as part of this
  chunk — any relationship between this idea and the existing JobSpy/JSearch integration is an
  open question (see "Ambiguities resolved" above), not a decision made here.

## Verification

Documentation-only checklist, not a test suite:

- Confirm this file is linked from `task-orchestration/README.md`'s "Side initiatives (pending
  Abhishek/multiagentic-system scoping)" grouping (grouped there for organizational consistency,
  even though this idea's specific blocker is a research pass, not the Abhishek conversation —
  see the note above).
- Confirm no other chunk in this doc set references this idea, or any specific MCP server/vendor
  for it, as if the research question above had already been answered.
