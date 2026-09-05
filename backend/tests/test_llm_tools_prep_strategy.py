"""Tests for the prep-strategy-suggestion prompt builders in app.clients.llm_tools.

Pure functions, no I/O — mirrors the style of test_cv_completeness.py.
"""

from __future__ import annotations

from app.clients.llm_tools import _PREP_STRATEGY_SYSTEM_PROMPT, build_prep_strategy_user_prompt
from app.domain.candidate import CVData


def test_prep_strategy_system_prompt_mentions_learning_style_and_timeline():
    assert "learning style" in _PREP_STRATEGY_SYSTEM_PROMPT.lower()
    assert "interview-ready" in _PREP_STRATEGY_SYSTEM_PROMPT.lower()


def test_build_prep_strategy_user_prompt_includes_style_and_timeline():
    cv = CVData(learning_style="visual", prep_timeline_weeks=4, desired_roles=["Backend Engineer"])
    prompt = build_prep_strategy_user_prompt(cv)
    assert "visual" in prompt
    assert "4" in prompt
    assert "Backend Engineer" in prompt


def test_build_prep_strategy_user_prompt_falls_back_when_no_desired_roles():
    cv = CVData(learning_style="reading", prep_timeline_weeks=2)
    prompt = build_prep_strategy_user_prompt(cv)
    assert "their target role" in prompt
