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
REQUIRED_FIELDS: list[str] = [
    "email",
    "phone",
    "linkedin_url",
    "technical_skills",
    "total_years_experience",
    "desired_roles",
    "desired_locations",
    "remote_preference",
]

# Contact/skills fields drive discoverability the most, so they carry more
# weight in completeness_score() than lower-value preference fields. Sums to
# 1.0. compute_missing_fields() intentionally stays unweighted/binary (see
# that function's docstring) — only the score below uses these weights.
FIELD_WEIGHTS: dict[str, float] = {
    "email": 0.15,
    "phone": 0.15,
    "linkedin_url": 0.15,
    "technical_skills": 0.20,
    "total_years_experience": 0.15,
    "desired_roles": 0.08,
    "desired_locations": 0.07,
    "remote_preference": 0.05,
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
    "technical_skills": "What are your top technical skills? (comma-separated is fine)",
    "total_years_experience": "How many years of professional experience do you have?",
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
