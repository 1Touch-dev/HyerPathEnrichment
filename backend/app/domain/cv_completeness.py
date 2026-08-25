"""Deterministic CV completeness rules. No I/O, no LLM calls.

Per Decision 1 (phase2_module2.md §3): completeness is computed here in plain
Python. The LLM is only used downstream, in the chatbot, to ask about — and
validate the format of — whichever fields this module says are missing.
"""

from __future__ import annotations

from app.domain.candidate import CVData

# Ordered by how strongly each field affects discoverability/matchability —
# asked in this order by the chatbot (§8.2) so the highest-value questions
# come first if a candidate abandons the session partway through.
#
# `github_url`, `portfolio_url`, and `highest_degree` (education) were added
# alongside the original contact/skills/preference fields — the original
# feature spec's completeness scan explicitly names GitHub, portfolio, and
# education as fields to check for, and `CVData` (app/domain/candidate.py)
# already has all three; they were simply never wired into this required-
# field list.
REQUIRED_FIELDS: list[str] = [
    "email",
    "phone",
    "linkedin_url",
    "github_url",
    "portfolio_url",
    "technical_skills",
    "total_years_experience",
    "highest_degree",
    "desired_roles",
    "desired_locations",
    "remote_preference",
]

# Contact/skills fields drive discoverability the most, so they carry more
# weight in completeness_score() than lower-value preference fields. Sums to
# 1.0. compute_missing_fields() intentionally stays unweighted/binary (see
# that function's docstring) — only the score below uses these weights.
FIELD_WEIGHTS: dict[str, float] = {
    "email": 0.13,
    "phone": 0.12,
    "linkedin_url": 0.12,
    "github_url": 0.07,
    "portfolio_url": 0.05,
    "technical_skills": 0.17,
    "total_years_experience": 0.12,
    "highest_degree": 0.06,
    "desired_roles": 0.07,
    "desired_locations": 0.05,
    "remote_preference": 0.04,
}

# List-type fields where a single entry is only partial signal — a richness
# factor (see completeness_score()) rewards candidates who provide several
# entries over just one.
_LIST_RICHNESS_FIELDS: frozenset[str] = frozenset(
    {"technical_skills", "desired_roles", "desired_locations"}
)
_RICHNESS_TARGET_COUNT = 3

FIELD_QUESTIONS: dict[str, str] = {
    "email": "What's the best email address for recruiters to reach you?",
    "phone": "What's a good phone number to include?",
    "linkedin_url": "Do you have a LinkedIn profile URL you'd like to include?",
    "github_url": "Do you have a GitHub profile? What's your username or profile URL?",
    "portfolio_url": "Do you have a portfolio site or personal website you'd like to link?",
    "technical_skills": "What are your top technical skills? (comma-separated is fine)",
    "total_years_experience": "How many years of professional experience do you have?",
    "highest_degree": "What's your highest level of education (degree and field of study)?",
    "desired_roles": "What job titles or roles are you targeting?",
    "desired_locations": "Which locations are you open to working in?",
    "remote_preference": "Do you prefer remote, hybrid, or onsite work?",
}


def compute_missing_fields(cv_data: CVData) -> list[str]:
    """Return the ordered list of required fields that are empty/None on cv_data.

    Mirrors the existing (private) `_calculate_completeness()` logic in
    `cv_extractor.py` but is exposed as its own module-level function so the
    chatbot and the documents router can both call it without importing a
    private method from a different module's internals (RULE.md: don't reach
    into another module's private implementation).
    """
    missing: list[str] = []
    for field_name in REQUIRED_FIELDS:
        value = getattr(cv_data, field_name, None)
        if value is None or isinstance(value, (list, str)) and len(value) == 0:
            missing.append(field_name)
    return missing


def completeness_score(cv_data: CVData) -> float:
    """0.0-1.0 weighted completeness score using FIELD_WEIGHTS.

    Missing fields (per `compute_missing_fields()`) contribute 0. For the
    list-type fields in `_LIST_RICHNESS_FIELDS`, a present-but-present field's
    weight contribution is scaled by a richness factor
    `min(1.0, len(value) / _RICHNESS_TARGET_COUNT)` so a single-item list
    scores partial credit rather than the full weight.
    """
    missing = compute_missing_fields(cv_data)
    score = 0.0
    for field_name in REQUIRED_FIELDS:
        if field_name in missing:
            continue
        weight = FIELD_WEIGHTS[field_name]
        if field_name in _LIST_RICHNESS_FIELDS:
            value = getattr(cv_data, field_name)
            richness = min(1.0, len(value) / _RICHNESS_TARGET_COUNT)
            score += weight * richness
        else:
            score += weight
    return round(score, 4)


def question_for_field(field_name: str) -> str:
    """The exact question text the chatbot asks for a given missing field."""
    return FIELD_QUESTIONS.get(field_name, f"Can you provide your {field_name.replace('_', ' ')}?")


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


def question_for_progressive_field(field_name: str) -> str:
    return PROGRESSIVE_FIELD_QUESTIONS.get(
        field_name, f"Can you tell us about your {field_name.replace('_', ' ')}?"
    )


def should_generate_prep_strategy_suggestion(cv_data: CVData) -> bool:
    """True exactly once per candidate — the moment both prep-relevant fields become
    known and no suggestion has been generated yet. Re-answering learning_style or
    prep_timeline_weeks later (e.g. candidate corrects an earlier answer) does not
    silently regenerate the suggestion — see cv_chat_service.py wiring note below for
    the explicit re-generation path instead."""
    return (
        cv_data.learning_style is not None
        and cv_data.prep_timeline_weeks is not None
        and cv_data.prep_strategy_suggestion is None
    )
