"""Shared OpenAI function-calling tool schema for the CV-completeness chatbot.

Per Decision 1 (phase2_module2.md §3): the model's only possible action besides
asking a question is to call `record_cv_answer` with an argument shape validated
by this schema — it cannot free-form invent CV field values outside this contract.
"""

from __future__ import annotations

from typing import Any

from app.domain.candidate import CVData

RECORD_CV_ANSWER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "record_cv_answer",
        "description": (
            "Record the candidate's answer for the specific CV field currently being asked about. "
            "Call this only when the candidate has provided a usable value; if their answer is unclear, "
            "ask a clarifying follow-up instead of calling this tool."
        ),
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "field_name": {
                    "type": "string",
                    "description": "The CVData field this answer is for.",
                },
                "value": {
                    "type": ["string", "null"],
                    "description": (
                        "The extracted value as a plain string, for scalar fields only. "
                        "Null if the current field is one of the list fields "
                        "(technical_skills, desired_roles, desired_locations); use "
                        "`values` for those instead."
                    ),
                },
                "values": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                    "description": (
                        "The extracted value as an array of strings, for the list fields "
                        "only (technical_skills, desired_roles, desired_locations). "
                        "Null if the current field is a scalar field; use `value` for those "
                        "instead."
                    ),
                },
            },
            "required": ["field_name", "value", "values"],
            "additionalProperties": False,
        },
    },
}


def build_chat_system_prompt(field_name: str, question: str) -> str:
    """System prompt for one chatbot turn — scoped to exactly one field at a time.

    Scoping to one field per turn (rather than a general "help complete this CV"
    system prompt) is what makes the turn-based, non-streamed design in Decision 2
    workable: each call is a small, bounded, cheap GPT-4o-mini request.
    """
    return (
        "You are a friendly assistant helping a job candidate complete their CV. "
        f"You are currently asking about ONE field: '{field_name}'. "
        f'Your question to the candidate is: "{question}" '
        "If the candidate's reply gives a usable answer for this field, call the "
        "record_cv_answer tool with field_name set. For scalar fields, populate `value` "
        "with a plain string answer and leave `values` null. For the three list fields "
        "(technical_skills, desired_roles, desired_locations), populate `values` with an "
        "array of strings and leave `value` null. If their reply is unrelated, "
        "unclear, or a question of their own, respond conversationally without calling "
        "the tool, and gently steer back to the question. Never invent a value the "
        "candidate did not provide."
    )


_PREP_STRATEGY_SYSTEM_PROMPT = (
    "You are an interview-prep coach. Given a candidate's preferred learning style and "
    "how many weeks they have until they need to be interview-ready, suggest a short, "
    "concrete interview-prep strategy tailored to that learning style and timeline. "
    "Be specific about *how* to use the time (e.g. what to prioritize in week 1 vs. "
    "the final week), not generic advice like 'practice more.' Keep it to 3-5 sentences "
    "or a short bulleted list. Do not repeat the candidate's own inputs back to them "
    "verbatim (e.g. don't open with 'Since you prefer visual learning and have 4 weeks...')."
)


def build_prep_strategy_user_prompt(cv_data: CVData) -> str:
    """User message for the one-off, free-text prep-strategy-suggestion call.

    No tool-calling needed here (unlike RECORD_CV_ANSWER_TOOL's structured-extraction
    call) — this is a single free-text generation, paired with
    `_PREP_STRATEGY_SYSTEM_PROMPT` as the system message.
    """
    timeline = cv_data.prep_timeline_weeks
    style = cv_data.learning_style
    desired_roles = (
        ", ".join(cv_data.desired_roles) if cv_data.desired_roles else "their target role"
    )
    return (
        f"Learning style: {style}\n"
        f"Weeks until interview-ready: {timeline}\n"
        f"Target role(s): {desired_roles}\n\n"
        "Suggest a concrete, time-boxed interview-prep strategy for this candidate."
    )
