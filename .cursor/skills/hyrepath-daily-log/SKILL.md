---
name: hyrepath-daily-log
description: >-
  Creates or updates HyrePath HQ Daily Logs for Aziz or Naved from plan + PR +
  git evidence, with a claim-honesty reviewer gate before Notion writes. Use when
  the user asks to daily log, close out today, update HyrePath HQ, log Aziz/Naved
  day, or sync today's tasks/status into Daily Logs.
---

# HyrePath Daily Log

Orchestrate a full Daily Log entry for **Aziz** or **Naved** in the HyrePath HQ **Daily Logs** database. Match the golden example body format. Never invent evidence. Never write Notion before the reviewer passes unless the user explicitly says `skip review`.

Read before acting:

- [references/notion-ids.md](references/notion-ids.md)
- [references/hq-rules.md](references/hq-rules.md)
- [references/area-defaults.md](references/area-defaults.md)
- [references/body-template.md](references/body-template.md)
- [../../agents/daily-log-reviewer.md](../../agents/daily-log-reviewer.md)

## Pipeline

```text
resolve developer+date → gather → gap draft → daily-log-reviewer → Notion sync → return URL
```

### 1. Resolve developer and date

- Developer must be `Aziz` or `Naved`. Ask if missing or ambiguous.
- Date defaults to today (`YYYY-MM-DD`) unless the user names another day.
- Row title: `{Developer} — {YYYY-MM-DD}`.

### 2. Gather

Collect a **source pack** (only what exists; do not invent):

| Source | How |
|---|---|
| User input | Chat, `@docs/daily/*.md`, or linked Notion page |
| Prior Daily Log | Query Daily Logs for same Developer + Date; also yesterday’s Left/Blocked for carry-over |
| Plan | `Today's plan` on prior row, template file, or user plan text |
| PR | User URL or `gh pr view` / list for the branch; capture title, body, checks, review state |
| Impl | `git log` / `git diff` vs base on the working branch; commit SHAs and notable paths |

If gather finds **no** plan, **no** PR, and **no** commits, ask before creating an empty log.

### 3. Gap analyzer — draft claim pack

Produce a draft object (in chat or scratch; not Notion yet):

- `Name`, `Developer`, `Date`, `Area` (default per area-defaults unless overridden)
- `Today's plan` — 1–3 concrete sentences
- Checklist under `## Today's tasks` with `[x]` / `[ ]` mapped from plan ↔ evidence
- Counts: `{done}/{total}`
- `Completed`, `Left`, `Notes / Why`, `Status` per hq-rules
- `PR`, `Other PRs` (real URLs only)
- `Milestone` relation URLs when known
- Full body markdown per body-template
- Evidence list (branch, PR, commits) — empty sections OK if nothing found

**Mapping rule:** a plan item is done only when PR and/or git evidence supports it. No evidence → Left / unchecked.

### 4. Reviewer gate

Apply [daily-log-reviewer](../../agents/daily-log-reviewer.md) to the claim pack (run as a readonly `reviewer` subagent with that file’s instructions, or follow the checklist yourself when subagents are unavailable).

- `fail` → revise the claim pack; do **not** write Notion
- `pass` / `pass-with-notes` → proceed (notes may be folded into Notes / Why)
- User said `skip review` → proceed with a one-line warning that review was skipped

### 5. Notion sync

Use Notion MCP only after pass (or skip).

1. `notion-fetch` Daily Logs DB / data source to confirm schema.
2. Query for existing row: same `Developer` + `date:Date:start` (or Name equals `{Developer} — {date}`).
3. **Create** with `notion-create-pages` parent `data_source_id` = `3923b3da-39c1-4372-a34a-44049796fa89`, **or update** with `notion-update-page`.
4. Set properties with exact names:

| Property | Format |
|---|---|
| `Name` | title string `{Developer} — YYYY-MM-DD` |
| `Developer` | `Aziz` or `Naved` |
| `date:Date:start` | `YYYY-MM-DD` |
| `date:Date:is_datetime` | `0` |
| `Area` | select |
| `Status` | select |
| `Today's plan` | text |
| `Completed` | text |
| `Left` | text |
| `Notes / Why` | text |
| `PR` | url or empty |
| `Other PRs` | text |
| `Milestone` | array of page URLs |

5. Body: Notion-flavored markdown from the draft (no duplicate title in content).
6. Fetch the page once to verify; return the Daily Log URL plus Status and `{done}/{total}`.

## Invoke examples

```text
Close out today for Aziz
Log Naved daily from @docs/daily/naved-TEMPLATE.md
Update HyrePath HQ for Aziz — 2026-09-04, PR https://github.com/1Touch-dev/HyerPathEnrichment/pull/123
Morning plan for Naved: …
```

## Hard stops

- Do not create a second Daily Logs database or free-floating wiki day pages under HQ for normal days.
- Do not mark `Completed` for code work without a PR URL.
- Do not invent commit SHAs or PR links.
- Do not commit or open a git PR as part of this skill unless the user separately asks.
