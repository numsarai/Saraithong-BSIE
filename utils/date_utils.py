"""
date_utils.py
-------------
Date/time parsing utilities for bank statement date fields.
Handles common Thai and international date formats.
"""

import re
from datetime import datetime, date
from typing import Optional

from dateutil import parser as dateutil_parser


# Common Thai/English date format patterns to try
_DATE_FORMATS = [
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y-%m-%d",
    "%d/%m/%y",
    "%d-%m-%y",
    "%Y%m%d",
    "%d %b %Y",
    "%d %B %Y",
    "%d/%m/%Y %H:%M:%S",
    "%d-%m-%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
]

# Thai Buddhist Era offset (BE = CE + 543)
_BE_THRESHOLD = 2400  # years > 2400 are likely BE


def _try_formats(text: str) -> Optional[datetime]:
    """Try each known format against text."""
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            continue
    return None


def _adjust_buddhist_era(dt: datetime) -> datetime:
    """Convert Buddhist Era year to Common Era if detected."""
    if dt.year > _BE_THRESHOLD:
        return dt.replace(year=dt.year - 543)
    return dt


def parse_date(value: object) -> Optional[date]:
    """
    Parse a date value from any reasonable representation.

    Handles:
    - datetime objects (passthrough)
    - date objects (passthrough)
    - strings with Thai/international formats
    - Buddhist ERA year correction
    - dateutil fallback

    Parameters
    ----------
    value : object
        Raw date value from Excel cell

    Returns
    -------
    date | None
    """
    if value is None:
        return None

    # Already a datetime or date
    if isinstance(value, datetime):
        return _adjust_buddhist_era(value).date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "nat", "-"}:
        return None

    # Try known formats
    dt = _try_formats(text)
    if dt:
        return _adjust_buddhist_era(dt).date()

    # Fallback: dateutil
    try:
        dt = dateutil_parser.parse(text, dayfirst=True)
        return _adjust_buddhist_era(dt).date()
    except (ValueError, OverflowError):
        pass

    return None


def parse_time(value: object) -> Optional[str]:
    """
    Parse a time value and return as HH:MM:SS string.

    Parameters
    ----------
    value : object
        Raw time value (datetime, time, str, float)

    Returns
    -------
    str | None  – "HH:MM:SS" or None
    """
    if value is None:
        return None

    if isinstance(value, datetime):
        return value.strftime("%H:%M:%S")

    if hasattr(value, 'hour'):  # datetime.time
        return value.strftime("%H:%M:%S")

    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "-"}:
        return None

    # Try HH:MM or HH:MM:SS
    m = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', text)
    if m:
        h, mn, s = m.group(1), m.group(2), m.group(3) or "00"
        return f"{int(h):02d}:{int(mn):02d}:{int(s):02d}"

    # Float from Excel (fraction of a day)
    try:
        f = float(text)
        total_seconds = int(round(f * 86400))
        h = total_seconds // 3600
        mn = (total_seconds % 3600) // 60
        s = total_seconds % 60
        return f"{h:02d}:{mn:02d}:{s:02d}"
    except ValueError:
        pass

    return None


def format_date_range(dates: list) -> str:
    """
    Format a list of date objects as "YYYY-MM-DD to YYYY-MM-DD".
    Returns empty string if no valid dates.
    """
    valid = [d for d in dates if d is not None]
    if not valid:
        return ""
    mn = min(valid)
    mx = max(valid)
    return f"{mn} to {mx}"
