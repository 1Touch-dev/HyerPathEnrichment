---
name: Plan Team Orchestrator
description: Use when asked to execute a large, multi-file implementation plan (a Markdown/spec document, often thousands of lines) using a team of subagents rather than doing all the work in a single continuous run. Applies to any plan document given at invocation time — this skill contains no reference to any specific plan, module, or codebase feature.
---

# Plan Team Orchestrator

You are acting as the master/orchestrating agent for a large implementation plan. This skill is intentionally generic: it describes a procedure, not a specific project. Every time it is invoked, treat the plan file given to you as the only source of truth for *what* to build — this skill only governs *how* you coordinate the work.

Do not assume the plan you were given today has the same file structure, dependency shape, or section numbering as any plan you may have orchestrated in a previous session. Re-derive everything below from scratch for the current plan.

## Step 0 — Ingest the plan

Read the full plan file (or files) given to you. If it is very large, read it section by section rather than trying to hold all of it verbatim in context at once — you will re-read specific sections again later when dispatching each chunk, so you do not need to memorize the whole thing now.

## Step 1 — Build a dependency graph before assigning any work

For every file the plan says to create or edit, determine:

- What other files-to-be-created it imports from or otherwise depends on.
- Which plan section/phase it belongs to (e.g. schema/migration, backend implementation, tests, infrastructure, frontend, docs).
- Whether it depends on a **state-changing action** rather than just another file — e.g. a database migration must actually be applied, a package must actually be installed, a config must actually be generated — before later work can build on it. State-changing actions cannot be parallelized against each other or against anything that reads the state they change.

Write this graph down explicitly (a short list is fine) before dispatching anything. Do not skip this step even if the plan looks simple — misjudging a hidden dependency is the most common way parallel execution silently breaks.

## Step 2 — Decide what is actually parallel-safe

Two chunks are parallel-safe only if **all** of the following hold:

- Neither chunk's files import, reference, or are imported/referenced by the other's files.
- Neither depends on a state-changing action the other also performs (e.g. both cannot migrate the same database).
- Neither is expected to edit a file the other also edits (shared config, shared type definitions, shared docs, etc.).

If you are not confident a pair of chunks meets all three, default to running them **sequentially, in one shared working copy**. This is the conservative default — a missed dependency is far more costly to untangle after the fact than a small amount of forgone parallelism.

Do not target a fixed team size (e.g. "5 developers"). The number of chunks that can genuinely run in parallel is an output of Step 1's graph for this specific plan, not an input you decide in advance. Cap total concurrent subagents at 8.

## Step 3 — Decide on isolation

- For chunks proven independent by Step 2, isolate each in its own git worktree so concurrent edits cannot collide. Reference `.cursor/worktrees.json` for setup (dependency install, env files) so each worktree is immediately buildable.
- For everything else, work in one shared worktree/branch, sequentially.
- If you did use separate worktrees for a parallel batch, you are responsible for reconciling them back into a single branch yourself once that batch completes — this does not happen automatically. Do this before moving to the next phase of the plan, not at the very end, so conflicts are caught early and small.

## Step 4 — Dispatch chunks

For each chunk, dispatch to a `developer` (implementation) or `tester` (test-writing/running) subagent with a fully self-contained prompt:

- The exact file paths involved.
- The exact spec/instruction text for those files, copied from the plan (not paraphrased/summarized from memory).
- Explicit files/directories that must not be touched.
- Any files the subagent may read for context but not edit.

## Step 5 — Gate with the reviewer after each chunk (or each small parallel-safe batch)

Dispatch the chunk's diff and its original spec to the `reviewer` subagent. Read its verdict:

- `pass` or `pass-with-notes` — proceed to the next chunk. Carry forward any notes so they are not lost.
- `fail` — do not proceed. Re-dispatch to a `developer` subagent with the reviewer's specific blocking issues as the new task, then re-review before moving on.

Do not batch multiple chunks' worth of work through a single review pass just to save time — the earlier a mismatch is caught, the cheaper it is to fix.

## Step 6 — Testing phase

Once an implementation phase is complete, identify which of its test files are independent of each other (per the same rule as Step 2 — no shared files, no shared state-changing action) and hand them to `tester` subagents, in parallel where genuinely independent, sequentially otherwise.

## Step 7 — Report progress continuously, not just at the end

After every chunk and every gate decision, post a short status update before continuing: what just finished, what the reviewer or tester reported, what is starting next. Do not go silent for an extended run and summarize only once everything is done — the person you're working for should be able to tell what is happening at any point without having to ask.

## Step 8 — Final integration and handoff

Once all chunks for the plan (or the portion you were asked to execute) are complete and reviewed:

1. Reconcile any remaining isolated worktrees into one branch.
2. Run the full validation the plan itself specifies (full test suite, migrations, lint/typecheck, build) — not just the narrow per-chunk checks used during Steps 4-6.
3. Follow this repository's own git/branch/PR rules for opening a pull request (see `.cursor/rules/`). Do not merge it yourself unless a rule explicitly permits that.
4. Report back what was built, what the final validation showed, and the PR link.
