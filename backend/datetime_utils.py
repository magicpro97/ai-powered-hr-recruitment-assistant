"""
Datetime utilities for API responses.

Convention: Store UTC in DB (TIMESTAMPTZ), return ISO 8601 UTC string with Z suffix in API responses.
"""

# Standard library imports
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def format_dt(dt) -> str:
    """Format a datetime for API response: ISO 8601 UTC string with Z suffix.

    Output example: 2026-02-09T12:00:00.123456Z
    The Z suffix ensures JavaScript's new Date() parses it as UTC.
    """
    if dt is None:
        return ""
    if isinstance(dt, datetime):
        return dt.replace(tzinfo=None).isoformat() + "Z"
    # Already a string — return as-is
    return str(dt)


def format_row_dates(row: dict, *keys: str) -> dict:
    """Return a new dict with specified datetime keys formatted as ISO strings."""
    result = dict(row)
    for key in keys:
        if key in result:
            result[key] = format_dt(result[key])
    return result
