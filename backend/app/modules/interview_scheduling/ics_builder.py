"""Hand-built .ics (RFC 5545) VEVENT generation and Google Calendar prefilled-link
builder — no third-party ICS dependency needed (Module 4, Module D §8.3)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode


def build_ics(
    *,
    uid: str,
    summary: str,
    description: str,
    location: str | None,
    start: datetime,
    duration_minutes: int,
    organizer_email: str,
) -> str:
    """Hand-built RFC 5545 VEVENT — minimal, no recurrence (RRULE not needed for a
    one-off interview), no attendee RSVP tracking (this is a personal reminder file
    for the candidate, not a real invite the interviewer receives — the candidate's
    own calendar app is the only consumer). DTSTART/DTEND in UTC (Z suffix) so the
    file is timezone-unambiguous regardless of which calendar app opens it.
    """
    start_utc = start.astimezone(UTC)
    end_utc = start_utc + timedelta(minutes=duration_minutes)
    now_utc = datetime.now(UTC)

    def _fmt(dt: datetime) -> str:
        return dt.strftime("%Y%m%dT%H%M%SZ")

    def _escape(text: str) -> str:
        # RFC 5545 §3.3.11: backslash, comma, semicolon must be escaped; literal
        # newlines become the two-char sequence \n.
        return (
            text.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;").replace("\n", "\\n")
        )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//HyerEnrichment//Interview Scheduling//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{_fmt(now_utc)}",
        f"DTSTART:{_fmt(start_utc)}",
        f"DTEND:{_fmt(end_utc)}",
        f"SUMMARY:{_escape(summary)}",
        f"DESCRIPTION:{_escape(description)}",
        f"ORGANIZER:mailto:{organizer_email}",
    ]
    if location:
        lines.append(f"LOCATION:{_escape(location)}")
    lines += ["STATUS:CONFIRMED", "END:VEVENT", "END:VCALENDAR"]
    # RFC 5545 §3.1 requires CRLF line endings, not bare \n.
    return "\r\n".join(lines) + "\r\n"


def build_google_calendar_link(
    *,
    summary: str,
    description: str,
    location: str | None,
    start: datetime,
    duration_minutes: int,
) -> str:
    """https://calendar.google.com/calendar/render?action=TEMPLATE&text=...&dates=...
    prefilled-link pattern — zero OAuth, opens Google Calendar's own "add event" UI
    with fields prefilled; the candidate still clicks "Save" themselves. This is the
    well-known Eventbrite/Calendly pattern flagged as [NotFound] (no specific citation
    pulled) but standard practice — used here as the low-friction alternative to the
    .ics download for candidates who prefer not to download a file.
    """
    start_utc = start.astimezone(UTC)
    end_utc = start_utc + timedelta(minutes=duration_minutes)
    dates = f"{start_utc.strftime('%Y%m%dT%H%M%SZ')}/{end_utc.strftime('%Y%m%dT%H%M%SZ')}"
    params = {"action": "TEMPLATE", "text": summary, "dates": dates, "details": description}
    if location:
        params["location"] = location
    return f"https://calendar.google.com/calendar/render?{urlencode(params)}"
