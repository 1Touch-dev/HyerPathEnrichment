# HyrePath HQ Daily Log rules

Source of truth: HyrePath HQ page body (“How we use this”).

## One row per person per day

- Title: `{Developer} — YYYY-MM-DD`
- Developers: Aziz and Naved only
- Query Daily Logs for an existing row with the same Developer + Date before creating

## Morning (plan)

Fill: Date, Developer, Area, Milestone (when known), **Today's plan** (1–3 concrete tasks).
Status = `Planned`. PR empty.
If more than one task, put a checklist in the page body under `## Today's tasks`.

## Close-out (status from evidence)

Derive from plan + PR + implementation (not wishful checkboxes):

1. **Completed** — all planned items done. For code work, **PR is required**. Optional one-liner in Completed. Prefer empty PR + `n/a` in Notes / Why only for docs/research with no code.
2. **Pending** or **Blocked** — fill Completed, Left, and Notes / Why. Link open/draft PR when it exists.
3. Extra PRs go in **Other PRs**.

A Completed day with no PR (for code work) is not closed — use Pending instead.

## Status decision table

| Situation | Status |
|---|---|
| All tasks done + PR (code) | `Completed` |
| All tasks done, docs/research only, no code | `Completed` (PR empty; Notes / Why = `n/a`) |
| Some left, no hard block | `Pending` |
| Explicit blocker | `Blocked` |
| Plan only, no progress | `Planned` |

## Honesty

- Never invent commits, PR URLs, or check results
- Plan item without evidence stays unchecked / Left
- Prefer under-claiming over over-claiming
