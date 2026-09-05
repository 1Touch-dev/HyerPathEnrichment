"""Sanitize user-controlled tokens before appending to subprocess argv."""

from __future__ import annotations


def sanitize_cli_arg(value: str, *, label: str = "argument") -> str:
    """Reject empty / NUL / leading-dash values that could be parsed as flags.

    Callers still use ``create_subprocess_exec`` (no shell). This only blocks
    option-injection via positional or ``--flag <value>`` slots.
    """
    cleaned = (value or "").strip()
    if not cleaned:
        raise ValueError(f"{label} must not be empty")
    if "\x00" in cleaned:
        raise ValueError(f"{label} must not contain NUL")
    if cleaned.startswith("-"):
        raise ValueError(f"{label} must not start with '-'")
    return cleaned
