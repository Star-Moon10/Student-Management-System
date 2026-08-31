"""China Standard Time helpers for all user-facing and persisted system timestamps."""

from datetime import datetime, timedelta, timezone
import re


CHINA_TIMEZONE = timezone(timedelta(hours=8), name="CST")
TIMEZONE_MIGRATION_KEY = "china_standard_time_v1"
_TIMESTAMP_TEXT = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")


def china_now() -> datetime:
    return datetime.now(CHINA_TIMEZONE)


def as_china_time(value: datetime | None) -> datetime | None:
    """Treat SQLite's naive persisted values as China local time after migration."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=CHINA_TIMEZONE)
    return value.astimezone(CHINA_TIMEZONE)


def legacy_utc_to_china(value: datetime) -> datetime:
    """Convert a pre-migration UTC value to a naive China-local database value."""
    utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
    return utc_value.astimezone(CHINA_TIMEZONE).replace(tzinfo=None)


def china_datetime_text(value: datetime | None, format_string: str = "%Y-%m-%d %H:%M:%S") -> str:
    local_value = as_china_time(value)
    return local_value.strftime(format_string) if local_value else ""


def normalize_timestamp_text(value: str) -> str:
    """Return a full CST ISO timestamp for a JSON date-time string, preserving dates alone."""
    if not _TIMESTAMP_TEXT.fullmatch(value):
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return as_china_time(parsed).isoformat()


def normalize_json_timestamps(value):
    if isinstance(value, str):
        return normalize_timestamp_text(value)
    if isinstance(value, list):
        return [normalize_json_timestamps(item) for item in value]
    if isinstance(value, dict):
        return {key: normalize_json_timestamps(item) for key, item in value.items()}
    return value
