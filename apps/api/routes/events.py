"""Event routes — aligned with FRONTEND_DATA_ACCESS.md."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from apps.api.dependencies import get_store
from apps.api.schemas.frontend import EventDetailResponse, EventListResponse
from apps.api.services.event_query import list_events_in_local_day, stored_event_to_detail
from apps.api.services.timezone_utils import InvalidTimezoneError
from event_maintainer.db import SQLiteEventStore

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/", response_model=EventListResponse)
async def list_events(
    event_date: date = Query(..., description="Calendar day in display timezone (YYYY-MM-DD)"),
    timezone: str = Query(..., description="IANA timezone, e.g. Asia/Shanghai"),
    page_size: int = Query(0, ge=0, description="Page size; 0 returns all for the day"),
    offset: int = Query(0, ge=0, description="Result offset"),
    source: Optional[str] = Query(None, description="Filter by source"),
    country: Optional[str] = Query(None, description="Filter by country"),
    category: Optional[str] = Query(None, description="Filter by category"),
    store: SQLiteEventStore = Depends(get_store),
):
    try:
        items, total, window = list_events_in_local_day(
            store,
            event_date,
            timezone,
            source=source,
            country=country,
            category=category,
            page_size=page_size,
            offset=offset,
        )
    except InvalidTimezoneError:
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {timezone}")

    return EventListResponse(
        items=items,
        total=total,
        limit=page_size if page_size > 0 else 0,
        offset=offset,
        query_window=window,
    )


@router.get("/{event_id}", response_model=EventDetailResponse)
async def get_event(
    event_id: str,
    store: SQLiteEventStore = Depends(get_store),
):
    event = store.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return stored_event_to_detail(event)
