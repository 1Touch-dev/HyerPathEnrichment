"""Deterministic job-match scoring. No LLM calls, no I/O — pure functions.

Per Decision 3 (phase2_module1.md §3): the overall_score is computed here and
passed INTO the LLM prompt as a given fact. The LLM never regenerates this number.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

# Weights sum to 1.0 — similarity dominates, rule-filters are a smaller adjustment.
# This is a product decision (not sourced from any paper) and is intentionally
# simple for v1; see Decision 2 for why a learned weighting model is out of scope.
SIMILARITY_WEIGHT = 0.7
RULE_WEIGHT = 0.3


def normalize_dedup_field(value: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation — used for both title and location."""
    value = value.lower().strip()
    value = re.sub(r"[^\w\s]", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def compute_dedup_key(title: str, location: str | None, source: str) -> str:
    """Per Decision 4: company name is deliberately excluded (Canaria's confirmed reasoning)."""
    normalized_title = normalize_dedup_field(title)
    normalized_location = normalize_dedup_field(location or "")
    source_domain = source.lower().strip()
    raw = f"{normalized_title}|{normalized_location}|{source_domain}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def score_salary_fit(
    posting_min: int | None,
    posting_max: int | None,
    pref_min: int | None,
    pref_max: int | None,
) -> float:
    """1.0 if fully compatible, 0.0 if fully incompatible, partial credit for overlap.

    Missing data on either side is treated as neutral (0.5) rather than penalized,
    since most scraped postings omit salary entirely.
    """
    if pref_min is None and pref_max is None:
        return 0.5  # candidate has no salary preference; neutral
    if posting_min is None and posting_max is None:
        return 0.5  # posting has no salary listed; neutral

    p_min = posting_min if posting_min is not None else 0
    p_max = posting_max if posting_max is not None else float("inf")
    c_min = pref_min if pref_min is not None else 0
    c_max = pref_max if pref_max is not None else float("inf")

    overlap_low = max(p_min, c_min)
    overlap_high = min(p_max, c_max)
    if overlap_low > overlap_high:
        return 0.0  # no overlap at all
    return 1.0


def score_location_fit(
    posting_location: str | None,
    posting_remote: bool,
    pref_locations: list[str],
    pref_remote: str | None,
) -> float:
    """1.0 for exact/remote match, 0.5 neutral if no preference stated, 0.0 for mismatch."""
    if pref_remote == "remote":
        return 1.0 if posting_remote else 0.0
    if not pref_locations:
        return 0.5  # no location preference stated
    if posting_remote:
        return 1.0  # remote satisfies any location preference

    normalized_pref = {normalize_dedup_field(loc) for loc in pref_locations}
    normalized_posting = normalize_dedup_field(posting_location or "")
    if any(pref in normalized_posting or normalized_posting in pref for pref in normalized_pref):
        return 1.0
    return 0.0


def compute_rule_score(
    posting: dict[str, Any],
    preferences: dict[str, Any],
) -> tuple[float, dict[str, float]]:
    """Combine salary + location rule checks into one 0.0-1.0 rule_score.

    Returns (rule_score, breakdown) so the breakdown can be stored and shown in the UI.
    """
    salary_fit = score_salary_fit(
        posting.get("salary_min"),
        posting.get("salary_max"),
        preferences.get("salary_min"),
        preferences.get("salary_max"),
    )
    location_fit = score_location_fit(
        posting.get("location"),
        posting.get("remote", False),
        preferences.get("desired_locations", []),
        preferences.get("remote_preference"),
    )
    rule_score = (salary_fit + location_fit) / 2
    return rule_score, {"salary_fit": salary_fit, "location_fit": location_fit}


def compute_overall_score(similarity_score: float, rule_score: float) -> float:
    """Weighted composite, scaled to 0-100 for display."""
    composite = (similarity_score * SIMILARITY_WEIGHT) + (rule_score * RULE_WEIGHT)
    return round(max(0.0, min(1.0, composite)) * 100, 2)
