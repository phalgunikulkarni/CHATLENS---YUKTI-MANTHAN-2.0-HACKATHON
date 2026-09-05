"""Shared input validation + timezone-aware helpers for Calendar + Tasks.

Raises ValidationError (mapped to HTTP 400 by the routes) with safe,
human-readable messages. Never leaks filesystem/credentials/stack traces.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, available_timezones

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TIME_RE = re.compile(r"^\d{2}:\d{2}$")
_PRIORITIES = ("low", "medium", "high")

# Cache the tz set once (large but cheap to keep).
_TZ_SET = None


class ValidationError(Exception):
    """User input failed validation (-> HTTP 400)."""


def require_nonempty(value: Optional[str], field: str) -> str:
    if value is None or not str(value).strip():
        raise ValidationError(f"{field} is required")
    return str(value).strip()


def valid_date(value: Optional[str], field: str = "date") -> str:
    v = require_nonempty(value, field)
    if not _DATE_RE.match(v):
        raise ValidationError(f"{field} must be YYYY-MM-DD")
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValidationError(f"{field} is not a real calendar date")
    return v


def valid_time(value: Optional[str], field: str = "time") -> str:
    v = require_nonempty(value, field)
    if not _TIME_RE.match(v):
        raise ValidationError(f"{field} must be HH:MM (24-hour)")
    hh, mm = v.split(":")
    if not (0 <= int(hh) <= 23 and 0 <= int(mm) <= 59):
        raise ValidationError(f"{field} is not a valid time of day")
    return v


def optional_time(value: Optional[str], field: str = "time") -> Optional[str]:
    if value is None or str(value).strip() == "":
        return None
    return valid_time(value, field)


def valid_timezone(value: Optional[str]) -> str:
    """Validate an IANA timezone; default to UTC if blank. Rejects unknown zones."""
    global _TZ_SET
    if value is None or not str(value).strip():
        return "UTC"
    v = str(value).strip()
    if _TZ_SET is None:
        _TZ_SET = available_timezones()
    if v not in _TZ_SET:
        raise ValidationError(f"unknown timezone {v!r}")
    return v


def valid_priority(value: Optional[str]) -> str:
    v = (value or "medium").strip().lower()
    if v not in _PRIORITIES:
        raise ValidationError("priority must be one of: low, medium, high")
    return v


def ensure_end_after_start(start: str, end: Optional[str]) -> None:
    """If an end time is supplied it must be strictly after the start time."""
    if end is None:
        return
    if end <= start:
        raise ValidationError("end_time must be after start_time")


def aware_datetime(date: str, time: str, tz: str) -> datetime:
    """Build a timezone-AWARE datetime for the user's local wall-clock time.

    This preserves the meaning of the user's local time (it does NOT reinterpret
    it as UTC). Callers may convert to UTC for storage/scheduling as needed.
    """
    naive = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
    return naive.replace(tzinfo=ZoneInfo(tz))
