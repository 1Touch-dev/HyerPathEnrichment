# Machine 2, Track 1 — Progressive Profiling Fields

## Goal

Add three new candidate-profile fields — `interests`, `learning_style`, `prep_timeline_weeks` —
to the CV completeness domain and the CV-chat chatbot, so placement-agency recruiters (and
direct candidates) get richer profiling data useful for interview-prep personalization and
job-fit matching. Confirmed (2026-08-22): none of these three fields exist today in
`backend/app/domain/cv_completeness.py` or `backend/app/domain/candidate.py`.

## Files to edit

- `backend/app/domain/candidate.py`
- `backend/app/domain/cv_completeness.py`
- `backend/app/clients/llm_tools.py`

## Files to create

- None — `CandidateDocument.extracted_data` is a flexible `JsonDoc` column
  (`backend/app/modules/documents/models.py` line 39); new `CVData` fields are stored inside it
  without a migration, exactly like every existing field. No new table, no new migration.

## `backend/app/domain/candidate.py` — `CVData`

Add to the `# Preferences` block (after `salary_expectation`, before `# Metadata`):

```python
    # Progressive profiling (interview-prep personalization)
    interests: list[str] = Field(default_factory=list)
    learning_style: str | None = None  # "visual"/"reading"/"hands_on"/"discussion" (free text otherwise)
    prep_timeline_weeks: int | None = None  # candidate's self-reported weeks until they need to be interview-ready
```

## `backend/app/domain/cv_completeness.py`

**Do not add these three fields to `REQUIRED_FIELDS`.** `REQUIRED_FIELDS` drives the mandatory
completeness gate (used for the discoverability/matchability score); `interests`,
`learning_style`, and `prep_timeline_weeks` are optional, "progressive profiling" fields —
nice-to-have for personalization, not required for a candidate to be considered "complete."
Making them required would silently lower every existing candidate's `completeness_score()` the
moment this ships, which is a behavior regression, not a feature.

Instead, add a **second, separate list** so the chatbot can ask about them only after the
required fields are resolved:

```python
# Progressive profiling — asked only after all REQUIRED_FIELDS are resolved (see
# cv_chat_service.py's session-completion branch). Optional: a candidate whose chat
# session ends before these are asked is still "completed", not "abandoned".
PROGRESSIVE_FIELDS: list[str] = [
    "interests",
    "learning_style",
    "prep_timeline_weeks",
]

PROGRESSIVE_FIELD_QUESTIONS: dict[str, str] = {
    "interests": "Outside of work, what are a few things you're genuinely interested in? (This helps us personalize interview prep and small talk.)",
    "learning_style": "When you're prepping for something new, do you learn best by reading, watching/visual examples, hands-on practice, or talking it through with someone?",
    "prep_timeline_weeks": "Roughly how many weeks do you have until you need to be interview-ready?",
}


def compute_missing_progressive_fields(cv_data: CVData) -> list[str]:
    """Same shape as compute_missing_fields() but over PROGRESSIVE_FIELDS — kept as a
    separate function (not merged into compute_missing_fields()) because these fields
    are optional and must never affect completeness_score() or the required-fields gate."""
    missing: list[str] = []
    for field_name in PROGRESSIVE_FIELDS:
        value = getattr(cv_data, field_name, None)
        if value is None or isinstance(value, (list, str)) and len(value) == 0:
            missing.append(field_name)
    return missing
```

Do not add a `question_for_field`-style single function shared between required and progressive
fields — keep `PROGRESSIVE_FIELD_QUESTIONS` and its own lookup separate so a future change to
required-field question wording can't accidentally change progressive-field wording (and
vice versa). Add:

```python
def question_for_progressive_field(field_name: str) -> str:
    return PROGRESSIVE_FIELD_QUESTIONS.get(
        field_name, f"Can you tell us about your {field_name.replace('_', ' ')}?"
    )
```

## `backend/app/modules/documents/cv_chat_service.py` — wiring (context only, verify before editing)

This file is listed as context, not required to edit for this chunk's minimum scope — the
required-fields chat flow (`start_session`/`post_message`) is unaffected. If the developer
subagent chooses to also wire progressive-field questions into the *same* chat session once
required fields complete (extending the "That's everything" branch at
`cv_chat_service.py` lines ~162-172 to instead ask progressive questions before marking
`completed`), that is an acceptable, encouraged extension of this chunk — but it must:

- Only change `CvChatService.post_message`'s post-required-fields branch, nothing else in that
  file.
- Track progressive-field answers the same way `fields_resolved` tracks required fields — either
  reuse `fields_resolved` (since `PROGRESSIVE_FIELDS` and `REQUIRED_FIELDS` are disjoint field
  names, no collision) or add a new `progressive_fields_resolved` JSON column on
  `CvChatSession` (`backend/app/modules/documents/models.py`) if kept separate — implementer's
  choice, but document which was chosen in the PR description since it affects
  `_apply_field_value`'s field-name-based branching (list fields vs. scalar fields — note
  `interests` is a list field like `technical_skills`, so it must be added to the `list_fields`
  set in `_apply_field_value`, line ~259, if wired).
- If `interests` is wired into `_apply_field_value`, add it to the `list_fields` set:
  `{"technical_skills", "desired_roles", "desired_locations", "interests"}`.

## `backend/app/clients/llm_tools.py` — `RECORD_CV_ANSWER_TOOL`

The tool's `field_name` parameter is currently a plain `"type": "string"` with no enum
constraint (verify this at implementation time — if an enum of valid field names has since been
added, extend that enum with the three new field names instead of leaving the schema
inconsistent). If it is unconstrained today, no change is strictly required here, but if an
enum exists, add `"interests"`, `"learning_style"`, `"prep_timeline_weeks"` to it.

## Do not touch

- `backend/app/modules/documents/models.py` — no migration needed (see "Files to create"); do
  not add new columns unless choosing the `progressive_fields_resolved` extension above, and if
  so, that is the *only* column to add.
- `backend/app/modules/job_matching/`, `backend/app/modules/outreach/`,
  `backend/app/modules/portfolio/`, `backend/app/modules/admin/` — untouched by this track.
- `REQUIRED_FIELDS`, `FIELD_WEIGHTS`, `FIELD_QUESTIONS`, `compute_missing_fields()`,
  `completeness_score()` in `cv_completeness.py` — read-only reference, not edited. This chunk
  only *adds* new module-level names; it does not change any existing one.

## Verification

- Add unit tests to whichever test file already covers `cv_completeness.py` (locate it under
  `backend/tests/` before assuming a path) asserting: a `CVData` with all `REQUIRED_FIELDS` set
  but no progressive fields still scores the same `completeness_score()` as before this change
  (regression check), and `compute_missing_progressive_fields()` correctly reports all three as
  missing when unset.
- If `cv_chat_service.py` was extended, add/extend its existing test module to cover the new
  post-required-fields branch.
