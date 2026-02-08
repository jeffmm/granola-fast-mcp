"""Timezone detection and formatting utilities."""

import time
import zoneinfo
from datetime import datetime

# Abbreviation → IANA timezone mapping (US-focused)
_TZ_ABBREV_MAP: dict[str, str] = {
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
}

# UTC offset (hours) → IANA timezone mapping (fallback)
_TZ_OFFSET_MAP: dict[int, str] = {
    -8: "America/Los_Angeles",
    -7: "America/Denver",
    -6: "America/Chicago",
    -5: "America/New_York",
    -4: "America/New_York",
}

_FALLBACK_TZ = "America/New_York"


def detect_local_timezone() -> zoneinfo.ZoneInfo:
    """Detect the local timezone from the system."""
    try:
        if hasattr(time, "tzname") and time.tzname:
            current_tz = time.tzname[time.daylight]
            if current_tz in _TZ_ABBREV_MAP:
                return zoneinfo.ZoneInfo(_TZ_ABBREV_MAP[current_tz])

        # Fallback: detect from system UTC offset
        local_offset = time.timezone if not time.daylight else time.altzone
        hours_offset = -local_offset // 3600
        if hours_offset in _TZ_OFFSET_MAP:
            return zoneinfo.ZoneInfo(_TZ_OFFSET_MAP[hours_offset])
    except Exception:
        pass

    return zoneinfo.ZoneInfo(_FALLBACK_TZ)


def convert_to_local(utc_dt: datetime, tz: zoneinfo.ZoneInfo) -> datetime:
    """Convert a datetime (assumed UTC if naive) to the given timezone."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=zoneinfo.ZoneInfo("UTC"))
    return utc_dt.astimezone(tz)


def format_local_time(utc_dt: datetime, tz: zoneinfo.ZoneInfo) -> str:
    """Format a datetime in the given local timezone for display."""
    return convert_to_local(utc_dt, tz).strftime("%Y-%m-%d %H:%M")
