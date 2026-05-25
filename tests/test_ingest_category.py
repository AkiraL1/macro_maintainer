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


def test_ingest_rejects_unregistered_category(
    tmp_path: Path, category_registry_file: Path
) -> None:
    context = build_app_context(_settings(tmp_path, category_registry_file))
    result = context.maintenance.ingest_events(
        [
            EventDraft(
                title="Odd tag",
                source="test",
                event_time="2026-05-23T00:00:00Z",
                raw_content="body",
                category="unknown_cat",
            )
        ]
    )

    assert result.inserted == 0
    assert result.rejected == 1
    assert len(context.store.list_events()) == 0
    logs = context.store.list_maintenance_logs()
    assert any(log["status"] == "rejected" for log in logs)


def test_ingest_accepts_registered_label(
    tmp_path: Path, category_registry_file: Path
) -> None:
    context = build_app_context(_settings(tmp_path, category_registry_file))
    result = context.maintenance.ingest_events(
        [
            EventDraft(
                title="FOMC",
                source="test",
                event_time="2026-05-23T00:00:00Z",
                raw_content="FOMC decision.",
                category="央行",
            )
        ]
    )

    assert result.inserted == 1
    assert result.rejected == 0
