"""Audio transcription analysis service for practice sessions.

Analyzes transcribed speech for filler words, speaking pace, and clarity metrics.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Filler words to detect
FILLER_WORDS = {
    "um",
    "uh",
    "like",
    "you know",
    "basically",
    "actually",
    "literally",
}

# Target speaking pace (words per minute)
TARGET_WPM_MIN = 120
TARGET_WPM_MAX = 180


@dataclass(slots=True)
class AudioAnalysis:
    """Analysis results for audio transcription."""

    word_count: int
    filler_word_count: int
    filler_word_percentage: float
    words_per_minute: float | None
    clarity_score: float
    detected_fillers: list[str]


def count_filler_words(text: str) -> tuple[int, list[str]]:
    """Count filler words in transcribed text.

    Args:
        text: Transcribed text

    Returns:
        Tuple of (total_filler_count, list_of_detected_fillers)
    """
    normalized_text = text.lower()
    detected_fillers = []

    for filler in FILLER_WORDS:
        # Use word boundaries for single-word fillers
        if " " not in filler:
            pattern = rf"\b{re.escape(filler)}\b"
            matches = re.findall(pattern, normalized_text)
            if matches:
                detected_fillers.extend(matches)
        else:
            # For multi-word fillers (e.g., "you know")
            count = normalized_text.count(filler)
            detected_fillers.extend([filler] * count)

    return len(detected_fillers), detected_fillers


def calculate_words_per_minute(word_count: int, duration_seconds: float | None) -> float | None:
    """Calculate speaking pace in words per minute.

    Args:
        word_count: Total word count
        duration_seconds: Audio duration in seconds

    Returns:
        Words per minute, or None if duration is unavailable
    """
    if duration_seconds is None or duration_seconds <= 0:
        return None

    duration_minutes = duration_seconds / 60.0
    return word_count / duration_minutes


def calculate_clarity_score(
    filler_percentage: float,
    wpm: float | None,
) -> float:
    """Calculate clarity score (0-100) based on filler words and speaking pace.

    Scoring formula:
    - Start at 100
    - Deduct 1 point for each 1% of filler words (max -30 points)
    - Deduct points for speaking too fast or too slow (max -20 points)

    Args:
        filler_percentage: Percentage of filler words (0-100)
        wpm: Words per minute (optional)

    Returns:
        Clarity score from 0 to 100
    """
    score = 100.0

    # Penalize filler words (1% filler = -1 point, capped at 30)
    filler_penalty = min(filler_percentage, 30.0)
    score -= filler_penalty

    # Penalize speaking pace if available
    if wpm is not None:
        if wpm < TARGET_WPM_MIN:
            # Too slow: penalize up to 20 points
            pace_penalty = min((TARGET_WPM_MIN - wpm) / 10.0, 20.0)
            score -= pace_penalty
        elif wpm > TARGET_WPM_MAX:
            # Too fast: penalize up to 20 points
            pace_penalty = min((wpm - TARGET_WPM_MAX) / 20.0, 20.0)
            score -= pace_penalty

    return max(0.0, min(100.0, score))


def analyze_transcription(
    transcription_text: str,
    duration_seconds: float | None = None,
) -> AudioAnalysis:
    """Analyze transcribed audio for filler words, pace, and clarity.

    Args:
        transcription_text: Transcribed text from Whisper
        duration_seconds: Optional audio duration in seconds

    Returns:
        AudioAnalysis with metrics and detected issues
    """
    # Count words (simple split on whitespace)
    words = transcription_text.split()
    word_count = len(words)

    if word_count == 0:
        logger.warning("Empty transcription provided for analysis")
        return AudioAnalysis(
            word_count=0,
            filler_word_count=0,
            filler_word_percentage=0.0,
            words_per_minute=None,
            clarity_score=0.0,
            detected_fillers=[],
        )

    # Count filler words
    filler_count, detected_fillers = count_filler_words(transcription_text)
    filler_percentage = (filler_count / word_count) * 100.0

    # Calculate speaking pace
    wpm = calculate_words_per_minute(word_count, duration_seconds)

    # Calculate clarity score
    clarity_score = calculate_clarity_score(filler_percentage, wpm)

    logger.info(
        "Transcription analysis complete",
        extra={
            "word_count": word_count,
            "filler_count": filler_count,
            "filler_percentage": round(filler_percentage, 2),
            "wpm": round(wpm, 2) if wpm else None,
            "clarity_score": round(clarity_score, 2),
        },
    )

    return AudioAnalysis(
        word_count=word_count,
        filler_word_count=filler_count,
        filler_word_percentage=round(filler_percentage, 2),
        words_per_minute=round(wpm, 2) if wpm else None,
        clarity_score=round(clarity_score, 2),
        detected_fillers=detected_fillers,
    )
