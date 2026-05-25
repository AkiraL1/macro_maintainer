from __future__ import annotations

import json
from pathlib import Path

from event_maintainer.app_context import build_app_context
from event_maintainer.config import AppSettings
from event_maintainer.schemas import EventDraft
from event_maintainer.sources import load_event_drafts


def _settings(tmp_path: Path, registry: Path) -> AppSettings:
    return AppSettings(
        db_path=tmp_path / "events.sqlite3",
        mem0_enabled=False,
        mem0_dup_threshold=1.01,
        category_registry_path=registry,
    )


def test_ingest_ordered_categories(tmp_path: Path, category_registry_file: Path) -> None:
    context = build_app_context(_settings(tmp_path, category_registry_file))
    draft_path = tmp_path / "drafts.json"
    draft_path.write_text(
        json.dumps(
            [
                {
                    "title": "FOMC holds rates",
                    "source": "Reuters",
                    "event_time": "2026-05-20T18:00:00Z",
                    "raw_content": "Fed held rates steady.",
                    "categories": ["央行", "宏观"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    drafts = load_event_drafts(draft_path)
    assert drafts[0].categories == ("央行", "宏观")
    assert drafts[0].category == "央行"

    result = context.maintenance.ingest_events(drafts)
    assert result.inserted == 1
    stored = context.store.list_events()[0]
    assert stored.draft.categories == ("央行", "宏观")
    assert stored.draft.category == "央行"

    api = context.store._stored_to_api_dict(stored)
    assert api["categories"] == ["央行", "宏观"]
    assert api["category"] == "央行"


def test_update_event_categories(tmp_path: Path, category_registry_file: Path) -> None:
    context = build_app_context(_settings(tmp_path, category_registry_file))
    stored = context.store.upsert_event(
        EventDraft(
            title="Payrolls",
            source="test",
            event_time="2026-05-23T00:00:00Z",
            raw_content="Strong payrolls.",
            category="经济",
        )
    )
    result = context.maintenance.update_event(
        stored.id, categories=("经济", "宏观")
    )
    assert result["updated"] is True
    event = context.store.get_event(stored.id)
    assert event is not None
    assert event.draft.categories == ("经济", "宏观")
    assert event.draft.category == "经济"


def test_category_filter_matches_secondary_label(
    tmp_path: Path, category_registry_file: Path
) -> None:
    context = build_app_context(_settings(tmp_path, category_registry_file))
    context.store.upsert_event(
        EventDraft(
            title="FOMC",
            source="test",
            event_time="2026-05-20T18:00:00Z",
            raw_content="Statement.",
            categories=("央行", "宏观"),
        )
    )
    from datetime import datetime, timezone

    start = datetime(2026, 5, 20, tzinfo=timezone.utc)
    end = datetime(2026, 5, 21, tzinfo=timezone.utc)
    by_macro, total = context.store.list_events_in_time_window(
        start, end, category="宏观"
    )
    assert total == 1
    assert by_macro[0].draft.categories[1] == "宏观"
