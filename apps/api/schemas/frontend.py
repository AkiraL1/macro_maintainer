"""Frontend API response schemas — aligned with docs/FRONTEND_DATA_ACCESS.md."""
from datetime import date, datetime, timezone
from typing import Annotated, List, Optional

from pydantic import BaseModel, Field, PlainSerializer


def _serialize_utc_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


UtcDateTime = Annotated[datetime, PlainSerializer(_serialize_utc_datetime, return_type=str)]


class KeyMetricResponse(BaseModel):
    id: Optional[str] = None
    name: str
    value: str
    previous_value: Optional[str] = None
    change: Optional[float] = None
    unit: Optional[str] = None


class QueryWindow(BaseModel):
    timezone: str
    event_date: date
    start_utc: UtcDateTime
    end_utc: UtcDateTime


class EventListItem(BaseModel):
    id: str
    title: str
    source: Optional[str] = None
    event_date: Optional[date] = None
    event_time: UtcDateTime
    impact_level: Optional[str] = None
    category: Optional[str] = Field(
        None, description="Primary category (highest relevance); same as categories[0]"
    )
    categories: List[str] = Field(
        default_factory=list,
        description="Registered labels ordered by relevance (index 0 = strongest)",
    )
    summary: Optional[str] = None
    content: Optional[str] = None
    country: Optional[str] = Field(
        None, description="ISO 3166-1 alpha-2 when set (e.g. US, CN)"
    )
    importance_score: Optional[float] = None
    impact_score: Optional[float] = None
    symbols: List[str] = Field(default_factory=list)


class EventListResponse(BaseModel):
    items: List[EventListItem]
    total: int
    limit: Optional[int] = None
    offset: int = 0
    query_window: Optional[QueryWindow] = None


class EventDetailResponse(EventListItem):
    end_time: Optional[UtcDateTime] = None
    duration: Optional[float] = None
    analysis: Optional[str] = None
    key_metrics: List[KeyMetricResponse] = Field(default_factory=list)
    related_assets: List[str] = Field(default_factory=list)
    related_event_ids: List[str] = Field(default_factory=list)


class SearchResultItem(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    event_date: Optional[date] = None
    event_time: UtcDateTime
    country: Optional[str] = Field(
        None, description="ISO 3166-1 alpha-2 when set (e.g. US, CN)"
    )
    highlights: List[str] = Field(default_factory=list)


class SearchResponse(BaseModel):
    results: List[SearchResultItem]
    total: int
