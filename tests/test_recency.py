from __future__ import annotations

from datetime import datetime, timedelta, timezone

from event_maintainer.recency import (
    classify_event_time,
    maintenance_window,
    suggested_search_queries,
)


def test_maintenance_window_72h_and_7d() -> None:
    ref = datetime(2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc)
    start, end, now = maintenance_window(ref, past_hours=72, future_days=7)
    assert now == ref
    assert start == ref - timedelta(hours=72)
    assert end == ref + timedelta(days=7)


def test_classify_recent_upcoming_outside() -> None:
    ref = datetime(2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc)
    assert (
        classify_event_time(
            ref - timedelta(hours=1), now=ref, past_hours=72, future_days=7
        )
        == "recent"
    )
    assert (
        classify_event_time(
            ref + timedelta(days=3), now=ref, past_hours=72, future_days=7
        )
        == "upcoming"
    )
    assert (
        classify_event_time(
            ref - timedelta(days=30), now=ref, past_hours=72, future_days=7
        )
        == "outside"
    )


def test_suggested_search_queries_non_empty() -> None:
    ref = datetime(2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc)
    queries = suggested_search_queries(ref)
    assert len(queries) >= 4
    assert any(q["phase"] == "recent" for q in queries)
    assert any(q["phase"] == "upcoming" for q in queries)
