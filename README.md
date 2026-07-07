# HyerEnrichment

A documentation-ready Next.js demo for **AZI-10 — HyerEnrichemnt**.

This repository currently ships a polished frontend walkthrough of the enrichment experience: a single-page intake form, a pipeline trace, and a merged dossier view backed by deterministic mock data. It is suitable for review, UI validation, and automated PR handoff.

## What was built for AZI-10

The implemented deliverable in this branch is a **frontend enrichment console** that demonstrates the intended Hyrepath enrichment workflow:

- request intake for one or more identifier types
- tier selection for `tier1` through `tier4`
- a pipeline overview showing the orchestration stages
- a merged dossier UI with:
  - LinkedIn photo asset metadata
  - social handles
  - verified email results
  - GitHub/org context
  - coworker signals
  - jobs and business intelligence
  - confidence breakdowns
- deterministic mocked enrichment output for fast local review

## Current stack

- Next.js 14
- React 18
- TypeScript 5

## Project structure

```text
app/
  layout.tsx
  page.tsx
components/
  DossierView.tsx
  HeroPanel.tsx
  IntakeForm.tsx
  PipelineOverview.tsx
src/lib/
  mock-data.ts
  types.ts
  utils.ts
docs/
  architecture-plan-azi-10-hyre-enrichment.md
```

## Setup

Install dependencies:

```bash
npm install
```

## Run locally

Start the development server:

```bash
npm run dev
```

Then open:

```text
http://localhost:3000
```

## Available scripts

```bash
npm run dev        # start local dev server
npm run build      # production build
npm run start      # run the built app
npm run lint       # Next.js lint
npm run typecheck  # TypeScript validation
```

## How the demo works

1. Enter at least one identifier such as email, LinkedIn URL, username, company, business query, or job search query.
2. Select the enrichment tiers to simulate.
3. Submit the form.
4. The UI calls `/api/enrich` and renders a completed mock enrichment job.
5. The dossier and pipeline views update together to show the merged result.

## Release readiness notes

This branch is release-ready as a **UI/demo deliverable** for the current codebase.

What is ready:

- local install and run flow is straightforward
- deterministic demo data supports stable screenshots and review
- UI components are separated by concern
- documentation now matches the implemented repository

What is not in this repo yet:

- the full Python/FastAPI backend described in the broader product specification
- real async job orchestration
- Redis/Postgres/RQ infrastructure
- live provider integrations
- production enrichment sidecars

## Related docs

- `docs/architecture-plan-azi-10-hyre-enrichment.md` — earlier architecture planning artifact
- `docs/IMPLEMENTATION_NOTES.md` — concise implementation and handoff notes
- `CHANGELOG.md` — ticket-level release notes
