# Post-Tenancy Features, Chunk 5 — Freelance Bidding System (Idea List Only)

## ⚠️ SEPARATE INITIATIVE — read this before anything else in this file

**Same treatment as `04-upsell-and-side-tools-initiative.md`: this chunk is not part of the core
placement platform, and this file does not spec an implementation.** It records James's
freelance-bidding idea at a scoping level only, so it isn't lost, pending the same
Abhishek/multiagentic-system conversation `04`'s file names as a hard block. Do not produce a
`Files to create`/`Files to edit` list, a migration plan, or an effort estimate for this idea —
none of that can be correctly decided before understanding how "integration to our multiagentic
system" constrains the design, per James's answer recorded in `04`'s file
("yeah, but using integration to our multiagentic system, talk to Abhishek" — the same answer
covers this idea, since it was given in response to the same decision-list round as the upsell
ideas).

## Depends on

- The Abhishek/multiagentic-system conversation (not yet held, as of 2026-08-25) — hard block, not
  a soft preference, same as `04-upsell-and-side-tools-initiative.md`. This file is grouped with
  that one and with `06-mcp-job-board-research.md` under `README.md`'s "Side initiatives (pending
  Abhishek/multiagentic-system scoping)" grouping — separate from the main Machine 1/Machine 2
  merge order, and with no dependency edges into or out of that main graph.

## The idea (recorded, not scoped)

**Auto-bidding on Upwork/freelance-platform projects on candidates' behalf**, using Multilogin
multi-agent accounts (the same operational Multilogin-profile-per-real-account pattern
`machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md`'s "Multilogin profile/account
management" section already establishes for LinkedIn — this idea would presumably reuse that same
operational discipline, one profile per one real account, applied to Upwork/freelance-platform
accounts instead of LinkedIn ones, though this file does not commit to that reuse as a design
decision, only names it as the obvious precedent already in this doc set).

Key characteristics James described, recorded as-is:

- **Bidding is automated**, not a human manually submitting each proposal — this is a
  meaningfully different automation posture than `06-linkedin-outreach-send.md`'s dual-mode
  design (manual default + human-triggered automated batch); this idea, as described, does not
  appear to have a manual-trigger-per-batch framing the way LinkedIn sending now does. Whether
  this idea needs the same kind of explicit human-trigger boundary `06`'s leadership-confirmed
  design uses is an open design question for whoever eventually scopes this chunk, not resolved
  here.
- **Deliberate underbidding of market rate** — bidding below what a human freelancer/agency would
  typically charge for the same project, presumably as a volume/win-rate strategy. This has real
  commercial and possibly platform-ToS implications (most freelance platforms have language about
  bidding practices/anti-abuse) that are not analyzed in this file — flagging that a ToS review
  analogous to this doc set's LinkedIn-specific `hiQ Labs v. LinkedIn` analysis has not been done
  for Upwork or any other named freelance platform, and should happen before implementation
  scoping, not just before launch.
- **Explicit cost tracking against AI-token spend and human-hours cost** — the system should know,
  per bid/per project, how much it costs (in LLM API spend and any human oversight time) to
  generate and manage a bid, presumably to evaluate whether the underbid-and-win strategy is
  actually profitable once operating costs are counted, not just whether it wins projects. No
  schema, metric definition, or reporting surface is specified here — this is recorded as a
  requirement characteristic of the eventual design, not a built feature.

## Ambiguities resolved

- **Does this reuse `12`'s Multilogin profile-per-account pattern as a firm design decision?**
  No — named as the obvious existing precedent in this doc set, not committed to. The actual
  design (including whether Multilogin is even the right tool for Upwork-account management, as
  opposed to LinkedIn-specific anti-detect needs) is for the eventual scoping pass, informed by
  the Abhishek conversation.
- **Should this file estimate whether underbidding is a sound business strategy?** No — recorded
  as James's stated approach, not evaluated for soundness here; that's a business-strategy
  question outside this file's scope, which is limited to preserving the idea accurately.

## Do not touch

- Do not create any new backend module, migration, schema, or router for this idea as part of
  this chunk — this file's only deliverable is itself.
- Do not extend `backend/app/integrations/multilogin/profile_pool.py` or
  `machine-2-parallel-tracks/12-linkedin-sourcing-intern-multilogin.md`'s existing LinkedIn-scoped
  design to cover Upwork/freelance-platform accounts as part of this chunk — any such reuse is a
  future design decision, not something to implement here.

## Verification

Documentation-only checklist, not a test suite:

- Confirm this file is linked from `task-orchestration/README.md`'s "Side initiatives (pending
  Abhishek/multiagentic-system scoping)" grouping.
- Confirm no other chunk in this doc set references this idea as if it were already scoped or in
  progress.
