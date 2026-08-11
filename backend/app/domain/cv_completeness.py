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
    """0.0-1.0 fraction of REQUIRED_FIELDS that are populated."""
    missing = compute_missing_fields(cv_data)
    return round(1.0 - (len(missing) / len(REQUIRED_FIELDS)), 4)


def question_for_field(field_name: str) -> str:
    """The exact question text the chatbot asks for a given missing field."""
    return FIELD_QUESTIONS.get(field_name, f"Can you provide your {field_name.replace('_', ' ')}?")
