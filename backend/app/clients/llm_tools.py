"""Shared OpenAI function-calling tool schema for the CV-completeness chatbot.

Per Decision 1 (phase2_module2.md §3): the model's only possible action besides
asking a question is to call `record_cv_answer` with an argument shape validated
by this schema — it cannot free-form invent CV field values outside this contract.
"""

from __future__ import annotations

from typing import Any

RECORD_CV_ANSWER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "record_cv_answer",
        "description": (
            "Record the candidate's answer for the specific CV field currently being asked about. "
            "Call this only when the candidate has provided a usable value; if their answer is unclear, "
            "ask a clarifying follow-up instead of calling this tool."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "field_name": {
                    "type": "string",
                    "description": "The CVData field this answer is for.",
                },
                "value": {
                    "type": "string",
                    "description": (
                        "The extracted value as a plain string. For list fields "
                        "(technical_skills, desired_roles, desired_locations), "
                        "provide a comma-separated string; the caller splits it."
                    ),
                },
            },
            "required": ["field_name", "value"],
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
        f"Your question to the candidate is: \"{question}\" "
        "If the candidate's reply gives a usable answer for this field, call the "
        "record_cv_answer tool with field_name and value. If their reply is unrelated, "
        "unclear, or a question of their own, respond conversationally without calling "
        "the tool, and gently steer back to the question. Never invent a value the "
        "candidate did not provide."
    )
