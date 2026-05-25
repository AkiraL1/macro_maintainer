"""IANA timezone helpers for frontend local-day queries."""
from datetime import date, datetime, timedelta, timezone
from typing import Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class InvalidTimezoneError(ValueError):
    """Raised when an IANA timezone identifier cannot be resolved."""


def parse_iana_timezone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise InvalidTimezoneError(name) from exc


def local_day_to_utc_window(
    event_date: date,
    tz: ZoneInfo,
) -> Tuple[datetime, datetime]:
    start_local = datetime(
        event_date.year,
        event_date.month,
        event_date.day,
        tzinfo=tz,
    )
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    return start_utc, end_utc
