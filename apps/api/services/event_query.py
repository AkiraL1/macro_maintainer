"""Event query helpers for FastAPI — reads from SQLiteEventStore (3 tables)."""
from datetime import date, datetime
from typing import List, Optional, Tuple

from event_maintainer.db import SQLiteEventStore, parse_event_time
from event_maintainer.schemas import StoredEvent

from apps.api.schemas.frontend import (
    EventDetailResponse,
    EventListItem,
    KeyMetricResponse,
    QueryWindow,
    SearchResultItem,
)
from apps.api.services.timezone_utils import local_day_to_utc_window, parse_iana_timezone

DEFAULT_DURATION_SECONDS = 3600.0


def compute_impact_level(importance_score: float, impact_score: float) -> str:
    score = impact_score if impact_score else importance_score
    if score >= 0.7:
        return "high"
    if score >= 0.4:
        return "medium"
    return "low"


def compute_duration(event_time: datetime, end_time: datetime | None) -> float:
    if end_time and event_time:
        seconds = (end_time - event_time).total_seconds()
        return max(seconds, 0.0)
    return DEFAULT_DURATION_SECONDS


def _build_highlights(title: str, summary: Optional[str], query: str) -> List[str]:
    text = f"{title} {summary or ''}".lower()
    highlights: List[str] = []
    for term in query.split():
        if len(term) < 2:
            continue
        if term.lower() in text and term not in highlights:
            highlights.append(term)
    return highlights[:10]


def stored_event_to_list_item(event: StoredEvent) -> EventListItem:
    draft = event.draft
    event_time = parse_event_time(draft.event_time)
    return EventListItem(
        id=event.id,
        title=draft.title,
        source=draft.source,
        event_date=event_time.date(),
        event_time=event_time,
        impact_level=compute_impact_level(draft.importance_score, draft.impact_score),
        category=draft.category or None,
        categories=list(draft.categories),
        summary=draft.summary or None,
        content=draft.content or draft.raw_content or None,
        country=draft.country or None,
        importance_score=draft.importance_score,
        impact_score=draft.impact_score,
        symbols=list(draft.symbols),
    )


def stored_event_to_detail(event: StoredEvent) -> EventDetailResponse:
    draft = event.draft
    event_time = parse_event_time(draft.event_time)
    end_time = parse_event_time(draft.end_time) if draft.end_time else None
    base = stored_event_to_list_item(event)
    return EventDetailResponse(
        **base.model_dump(),
        end_time=end_time,
        duration=compute_duration(event_time, end_time),
        analysis=draft.analysis or None,
        key_metrics=[
            KeyMetricResponse(
                id=m.id,
                name=m.name,
                value=m.value,
                previous_value=m.previous_value,
                change=m.change,
                unit=m.unit,
            )
            for m in draft.key_metrics
        ],
        related_assets=list(draft.symbols),
        related_event_ids=list(draft.related_event_ids),
    )


def list_events_in_local_day(
    store: SQLiteEventStore,
    event_date: date,
    timezone_name: str,
    *,
    source: Optional[str] = None,
    country: Optional[str] = None,
    category: Optional[str] = None,
    page_size: int = 0,
    offset: int = 0,
) -> Tuple[List[EventListItem], int, QueryWindow]:
    tz = parse_iana_timezone(timezone_name)
    start_utc, end_utc = local_day_to_utc_window(event_date, tz)
    limit = None if page_size == 0 else page_size
    events, total = store.list_events_in_time_window(
        start_utc,
        end_utc,
        source=source,
        country=country,
        category=category,
        offset=offset,
        limit=limit,
    )
    window = QueryWindow(
        timezone=timezone_name,
        event_date=event_date,
        start_utc=start_utc,
        end_utc=end_utc,
    )
    return [stored_event_to_list_item(e) for e in events], total, window


def search_events(
    store: SQLiteEventStore,
    query: str,
    *,
    limit: int = 20,
) -> Tuple[List[SearchResultItem], int]:
    events, total = store.search_events_text(query, limit=limit)
    results: List[SearchResultItem] = []
    for event in events:
        draft = event.draft
        event_time = parse_event_time(draft.event_time)
        results.append(
            SearchResultItem(
                id=event.id,
                title=draft.title,
                summary=draft.summary or None,
                event_date=event_time.date(),
                event_time=event_time,
                country=draft.country or None,
                highlights=_build_highlights(draft.title, draft.summary, query),
            )
        )
    return results, total
