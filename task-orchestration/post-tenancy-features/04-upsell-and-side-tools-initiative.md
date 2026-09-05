# Post-Tenancy Features, Chunk 4 — Upsell and Side-Tools Initiative (Idea List Only)

## ⚠️ SEPARATE INITIATIVE — read this before anything else in this file

**This chunk is not part of the core placement platform, and this file does not spec an
implementation.** It exists solely to record a list of ideas from leadership (James) so they are
not lost between now and a scoping conversation that has not happened yet. Per James's own answer
to a decision-list question about this scope — **"yeah, but using integration to our multiagentic
system, talk to Abhishek"** — every idea below must integrate with an existing internal
multi-agent system that Abhishek owns, and no implementation detail, file list,
dependency graph, or effort estimate should be produced for any of them until that conversation
happens. Nothing in this file should be treated as ready to dispatch to a developer subagent.

Do not create a `Files to create`/`Files to edit` section for any of the four ideas below — that
would imply a scoping decision (module layout, migration ownership, etc.) that has not been made
and cannot correctly be made without first understanding how "integration to our multiagentic
system" constrains the design. Recording the idea list, and recording the blocking dependency on
the Abhishek conversation, is this file's entire job.

## Depends on

- The Abhishek/multiagentic-system conversation (not yet held, as of 2026-08-25) — this is a hard
  block on any further scoping, not a soft preference. Nothing in `machine-1-tenancy-core/` or
  `machine-2-parallel-tracks/` depends on this file, and this file depends on nothing else in this
  doc set; it is intentionally disconnected from the main Machine 1/Machine 2 merge graph (see
  `README.md`'s dependency graph and merge-order sections for how this and its two sibling chunks
  — `05-freelance-bidding-system.md`, `06-mcp-job-board-research.md` — are grouped as "Side
  initiatives," separate from the main tenancy-core/parallel-tracks ordering).

## The idea list (recorded, not scoped)

### (a) Tech-consulting / go-to-market upsell for high-value placements, leveraging "1touch.ai"

For high-value candidate placements, offer a tech-consulting or go-to-market advisory upsell to
the hiring company, leveraging an existing "1touch.ai" project/tech stack James referenced. No
detail on what "1touch.ai" currently does, what stage it's at, or how it would integrate with this
platform's placement flow is available yet — this needs its own discovery pass before any
scoping, separate even from the Abhishek multiagentic-system conversation (this sub-idea's open
question is "what is 1touch.ai and what does it already do," not primarily a multiagentic-
integration question, though that may also apply once more is known).

### (b) Free-course / certificate / project-building suggestions as a resume-improvement upsell

Suggest free courses, certificates, or small portfolio-building projects to a candidate to
quickly improve their resume — positioned especially as an upsell attached to high-value
applications (e.g. "this role wants X skill you're close on; here's a fast way to close that
gap before we submit you"). This is thematically adjacent to, but explicitly separate from,
`machine-2-parallel-tracks/01-progressive-profiling-fields.md`'s existing prep-strategy-suggestion
feature (interview-prep coaching once `learning_style`/`prep_timeline_weeks` are known) — that
existing feature is about interview *prep*, not resume *content* improvement via external
credentials, and this idea should not be folded into that chunk's scope without an explicit
decision to do so later. No scoping (which courses/providers, how "close on a skill" gets
detected, whether this is LLM-suggested or curated) is done here.

### (c) Competitor content/ad-analysis tool

A tool to analyze competitor placement agencies' content and advertising — presumably to inform
this platform's own marketing/positioning. No detail yet on which competitors, which channels
(social ads, job-board listings, SEO content), or what output format ("here's what they're doing"
vs. an actionable recommendation) is available. Recorded as an idea only.

### (d) Apify-based lead/email scraper

Use Apify (a web-scraping/automation platform) to build a lead-generation and email-scraping
tool — presumably for sourcing either candidate leads or hiring-company/recruiter contacts,
though James's answer did not specify which. **Note the adjacency to this doc set's existing
LinkedIn legal-risk sections** (`machine-2-parallel-tracks/06-linkedin-outreach-send.md`'s and
`12-linkedin-sourcing-intern-multilogin.md`'s risk analyses, both citing `hiQ Labs v. LinkedIn`) —
if this idea's eventual scope involves scraping LinkedIn or any other platform with contractual
anti-scraping terms, the same class of legal exposure those two chunks analyze in detail would
apply here too, and should be read before any implementation scoping begins. This file does not
resolve that risk or decide whether/how this idea would use Apify against LinkedIn specifically
versus other, less contractually-restricted sources — that is exactly the kind of decision that
needs the Abhishek conversation plus, likely, the same leadership risk-acceptance treatment
`06-linkedin-outreach-send.md`'s "Confirmed by leadership" section documents for LinkedIn sending
automation.

## Ambiguities resolved

- **Should this file attempt to estimate effort, propose a module layout, or sequence these four
  ideas relative to each other or to the main Machine 1/Machine 2 work?** No — explicitly rejected
  per the instruction at the top of this file. Any such estimate would be fabricated confidence
  about a system (the multiagentic system Abhishek owns) this doc set's authors have no visibility
  into yet.
- **Should any of these four ideas be merged into an existing chunk's scope (e.g. (b) into
  `01-progressive-profiling-fields.md`'s prep-strategy feature)?** No — deliberately kept
  separate for now, even where thematically adjacent, so that this initiative's later scoping
  (once the Abhishek conversation happens) isn't constrained by having already been half-merged
  into an unrelated chunk's design.

## Do not touch

- Do not create any new backend module, migration, schema, or router for any of the four ideas
  above as part of this chunk — this file's only deliverable is itself (the recorded idea list).
- Do not modify any existing chunk's scope to accommodate these ideas (see "Ambiguities resolved"
  above) without an explicit future decision to do so.

## Verification

Documentation-only checklist, not a test suite:

- Confirm this file is linked from `task-orchestration/README.md`'s "Side initiatives (pending
  Abhishek/multiagentic-system scoping)" grouping, clearly separated from the main Machine 1/
  Machine 2 merge order.
- Confirm no other chunk in this doc set references any of the four ideas above as if they were
  already scoped or in progress.
