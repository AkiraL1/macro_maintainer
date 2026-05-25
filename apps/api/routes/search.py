"""Search routes — SQLite LIKE on events table."""
from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_store
from apps.api.schemas.frontend import SearchResponse
from apps.api.services.event_query import search_events
from event_maintainer.db import SQLiteEventStore

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query text"),
    limit: int = Query(20, ge=1, le=100, description="Result limit"),
    store: SQLiteEventStore = Depends(get_store),
):
    results, total = search_events(store, q, limit=limit)
    return SearchResponse(results=results, total=total)
