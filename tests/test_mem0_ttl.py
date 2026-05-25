from __future__ import annotations

from datetime import date, datetime, timezone

from event_maintainer.config import AppSettings
from event_maintainer.memory.mem0_store import (
    Mem0MemoryStore,
    expires_on_date,
    is_metadata_expired,
)
from event_maintainer.schemas import EventDraft


def test_expires_on_date_adds_ttl_days() -> None:
    anchor = datetime(2026, 5, 24, tzinfo=timezone.utc)
    assert expires_on_date(30, now=anchor) == "2026-06-23"


def test_is_metadata_expired_after_expiry_day() -> None:
    assert is_metadata_expired({"expires_on": "2026-05-23"}, today=date(2026, 5, 24))
    assert not is_metadata_expired({"expires_on": "2026-05-23"}, today=date(2026, 5, 23))
    assert not is_metadata_expired({}, today=date(2026, 5, 24))


def test_local_search_skips_expired_memories(tmp_path) -> None:
    store = Mem0MemoryStore(
        AppSettings(db_path=tmp_path / "x.sqlite3", mem0_enabled=False, mem0_ttl_days=30)
    )
    store._local_memories.append(("old event", "id-1", "2020-01-01"))
    store._local_memories.append(("fresh event", "id-2", "2099-01-01"))
    draft = EventDraft(
        title="fresh event",
        source="test",
        event_time="2026-05-24T00:00:00Z",
        raw_content="fresh",
    )
    results = store.search_similar_events(draft)
    assert len(results) == 1
    assert results[0].event_id == "id-2"
