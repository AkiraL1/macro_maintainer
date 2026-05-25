from __future__ import annotations

from pathlib import Path

from event_maintainer.app_context import build_app_context
from event_maintainer.config import AppSettings
from event_maintainer.schemas import EventDraft

_TEST_REGISTRY = """---
categories:
  - label: 央行
    aliases: [monetary_policy, central_bank]
  - label: 宏观
    aliases: [macro]
  - label: 经济
    aliases: [labor_market, economy]
  - label: 加密货币
    aliases: [crypto]
---
"""


def _settings(tmp_path: Path) -> AppSettings:
    registry = tmp_path / "event_category.mdc"
    registry.write_text(_TEST_REGISTRY, encoding="utf-8")
    return AppSettings(
        db_path=tmp_path / "events.sqlite3",
        mem0_enabled=False,
        mem0_dup_threshold=1.01,
        category_registry_path=registry,
    )


def test_ingest_new_event_writes_database(tmp_path: Path) -> None:
    context = build_app_context(_settings(tmp_path))
    draft = EventDraft(
        title="Fed signals slower rate cuts",
        source="test-source",
        event_time="2026-05-23T00:00:00Z",
        raw_content="The Federal Reserve signaled a slower pace of rate cuts.",
        summary="Fed rate cut expectations cooled.",
        country="US",
        category="央行",
    )

    result = context.maintenance.ingest_events([draft])

    assert result.inserted == 1
    assert result.skipped_duplicates == 0
    assert result.rejected == 0
    assert len(context.store.list_events()) == 1


def test_duplicate_event_is_skipped(tmp_path: Path) -> None:
    context = build_app_context(_settings(tmp_path))
    draft = EventDraft(
        title="ECB holds rates",
        source="test-source",
        event_time="2026-05-23T08:00:00Z",
        raw_content="The ECB held benchmark rates steady.",
        summary="ECB kept rates unchanged.",
        country="EU",
        category="央行",
    )

    first = context.maintenance.ingest_events([draft])
    second = context.maintenance.ingest_events([draft])

    assert first.inserted == 1
    assert second.inserted == 0
    assert second.skipped_duplicates == 1


def test_missing_fields_are_logged_for_completion(tmp_path: Path) -> None:
    context = build_app_context(_settings(tmp_path))
    draft = EventDraft(
        title="Japan inflation data released",
        source="test-source",
        event_time="2026-05-23T09:00:00Z",
        raw_content="Japan released new inflation data.",
    )

    result = context.tools.upsert_event(draft)

    assert result["inserted"] == 1
    assert result["needs_completion"] == 1


def test_database_tools_expose_init_status_and_reads(tmp_path: Path) -> None:
    context = build_app_context(_settings(tmp_path))
    draft = EventDraft(
        title="US payrolls surprise markets",
        source="test-source",
        event_time="2026-05-23T10:00:00Z",
        raw_content="US payrolls were stronger than expected.",
        summary="Payrolls beat expectations.",
        country="US",
        category="经济",
    )

    init_status = context.tools.init_database()
    context.tools.upsert_event(draft)
    context.tools.upsert_event(draft)
    events = context.tools.search_events()
    event_id = str(events[0]["id"])
    current_status = context.tools.database_status()

    assert set(init_status["tables"]) == {
        "event_duplicates",
        "events",
        "maintenance_logs",
    }
    assert current_status["row_counts"]["events"] == 1
    assert current_status["row_counts"]["event_duplicates"] == 1
    assert context.tools.get_event(event_id)["id"] == event_id
