from __future__ import annotations

from pathlib import Path

from event_maintainer.app_context import build_app_context
from event_maintainer.config import AppSettings
from event_maintainer.schemas import EventDraft


def _settings(tmp_path: Path, registry: Path) -> AppSettings:
    return AppSettings(
        db_path=tmp_path / "events.sqlite3",
        mem0_enabled=False,
        mem0_dup_threshold=1.01,
        category_registry_path=registry,
    )


def test_update_event_maps_category(
    tmp_path: Path, category_registry_file: Path
) -> None:
    context = build_app_context(_settings(tmp_path, category_registry_file))
    ingest = context.maintenance.ingest_events(
        [
            EventDraft(
                title="Payrolls",
                source="test",
                event_time="2026-05-23T00:00:00Z",
                raw_content="Strong payrolls.",
                category="labor_market",
            )
        ]
    )
    assert ingest.rejected == 1

    draft = EventDraft(
        title="Payrolls",
        source="test",
        event_time="2026-05-23T00:00:00Z",
        raw_content="Strong payrolls.",
        category="",
    )
    stored = context.store.upsert_event(draft)
    result = context.maintenance.update_event(stored.id, category="经济")

    assert result["updated"] is True
    assert context.store.get_event(stored.id).draft.category == "经济"


def test_update_event_rejects_unregistered(
    tmp_path: Path, category_registry_file: Path
) -> None:
    context = build_app_context(_settings(tmp_path, category_registry_file))
    stored = context.store.upsert_event(
        EventDraft(
            title="Mystery",
            source="test",
            event_time="2026-05-23T00:00:00Z",
            raw_content="Unknown category event.",
            category="unknown_cat",
        )
    )

    result = context.maintenance.update_event(stored.id, category="not_registered")

    assert result["updated"] is False
    assert "not registered" in str(result["error"])
