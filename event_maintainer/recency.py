"""Maintenance recency window: past 72h + upcoming 7d (releases, briefings, etc.)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

PAST_HOURS_DEFAULT = 72
FUTURE_DAYS_DEFAULT = 7


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    return int(raw)


def maintenance_past_hours() -> int:
    raw = os.getenv("MAINTENANCE_PAST_HOURS", "").strip()
    if raw:
        return int(raw)
    from event_maintainer.project_settings import maintenance_past_hours_from_settings

    return maintenance_past_hours_from_settings()


def maintenance_future_days() -> int:
    raw = os.getenv("MAINTENANCE_FUTURE_DAYS", "").strip()
    if raw:
        return int(raw)
    from event_maintainer.project_settings import maintenance_future_days_from_settings

    return maintenance_future_days_from_settings()


def maintenance_window(
    now: datetime | None = None,
    *,
    past_hours: int | None = None,
    future_days: int | None = None,
) -> tuple[datetime, datetime, datetime]:
    """Return (window_start_utc, window_end_utc, reference_now_utc)."""
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    hours = past_hours if past_hours is not None else maintenance_past_hours()
    days = future_days if future_days is not None else maintenance_future_days()
    start = ref - timedelta(hours=hours)
    end = ref + timedelta(days=days)
    return start, end, ref


def classify_event_time(
    event_time: datetime,
    *,
    now: datetime | None = None,
    past_hours: int | None = None,
    future_days: int | None = None,
) -> str:
    """``recent`` | ``upcoming`` | ``outside`` relative to the maintenance window."""
    start, end, ref = maintenance_window(
        now, past_hours=past_hours, future_days=future_days
    )
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    if start <= event_time <= ref:
        return "recent"
    if ref < event_time <= end:
        return "upcoming"
    return "outside"


def suggested_search_queries(
    now: datetime | None = None,
    *,
    past_hours: int | None = None,
    future_days: int | None = None,
) -> list[dict[str, str]]:
    """DuckDuckGo query hints for Agent maintenance (English queries work best)."""
    start, end, ref = maintenance_window(
        now, past_hours=past_hours, future_days=future_days
    )
    month_year = ref.strftime("%B %Y")
    week_ahead = (ref + timedelta(days=7)).strftime("%Y-%m-%d")
    past_label = f"last {past_hours or maintenance_past_hours()} hours"
    return [
        {
            "phase": "recent",
            "query": f"US economic data release {past_label} {month_year}",
            "note": "已公布数据：CPI、非农、GDP、零售等",
        },
        {
            "phase": "recent",
            "query": f"Federal Reserve FOMC statement press conference {month_year}",
            "note": "央行：利率决议、声明、鲍威尔发布会",
        },
        {
            "phase": "upcoming",
            "query": f"US economic calendar releases week of {week_ahead}",
            "note": "未来7天日程：发布会、报告公布时间",
        },
        {
            "phase": "upcoming",
            "query": f"earnings macro calendar central bank speeches {month_year}",
            "note": "宏观/央行讲话与重要日程",
        },
        {
            "phase": "recent",
            "query": f"bitcoin crypto market news {past_label}",
            "note": "加密货币：监管、ETF、重大行情",
        },
    ]


def window_payload(
    now: datetime | None = None,
    *,
    past_hours: int | None = None,
    future_days: int | None = None,
) -> dict[str, object]:
    start, end, ref = maintenance_window(
        now, past_hours=past_hours, future_days=future_days
    )
    hours = past_hours if past_hours is not None else maintenance_past_hours()
    days = future_days if future_days is not None else maintenance_future_days()
    return {
        "reference_now_utc": ref.isoformat(),
        "window_start_utc": start.isoformat(),
        "window_end_utc": end.isoformat(),
        "past_hours": hours,
        "future_days": days,
        "policy": (
            "ingest 优先：event_time 落在 [window_start, reference_now] 的已发生事件，"
            "以及 (reference_now, window_end] 的即将发生事件（发布会、数据公布等）；"
            "窗口外仅纠错，不主动扩库"
        ),
        "suggested_searches": suggested_search_queries(
            ref, past_hours=hours, future_days=days
        ),
    }
