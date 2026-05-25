from __future__ import annotations

from pathlib import Path

import pytest

from event_maintainer.app_context import build_app_context
from event_maintainer.category import load_registry, run_category_audit
from event_maintainer.config import AppSettings
from event_maintainer.schemas import EventDraft


def _settings(tmp_path: Path, registry: Path) -> AppSettings:
    return AppSettings(
        db_path=tmp_path / "events.sqlite3",
        mem0_enabled=False,
        mem0_dup_threshold=1.01,
        category_registry_path=registry,
    )


def test_registry_fixture_has_four_labels(category_registry_file: Path) -> None:
    registry = load_registry(category_registry_file)
    assert len(registry.labels) == 4


def test_category_audit_flags_alias_and_missing(
    tmp_path: Path, category_registry_file: Path
) -> None:
    registry = load_registry(category_registry_file)
    context = build_app_context(_settings(tmp_path, category_registry_file))
    context.store.upsert_event(
        EventDraft(
            title="Fed holds",
            source="test",
            event_time="2026-05-23T00:00:00Z",
            raw_content="Fed held rates.",
            category="monetary_policy",
        )
    )

    report = run_category_audit(context.store, registry)

    assert report["needs_maintenance"] is True
    assert "宏观" in report["issues"]["registered_missing_in_db"]
    assert len(report["issues"]["alias_only"]) == 1
    assert report["issues"]["alias_only"][0]["suggest"] == "央行"


def test_category_audit_clean_when_labels_used(
    tmp_path: Path, category_registry_file: Path
) -> None:
    registry = load_registry(category_registry_file)
    context = build_app_context(_settings(tmp_path, category_registry_file))
    for index, label in enumerate(("央行", "宏观", "经济", "加密货币")):
        result = context.maintenance.ingest_events(
            [
                EventDraft(
                    title=f"Event {label}",
                    source="test",
                    event_time=f"2026-05-23T{index:02d}:00:00Z",
                    raw_content=f"unique body for {label}",
                    category=label,
                )
            ]
        )
        assert result.inserted == 1, (
            f"{label}: inserted={result.inserted} "
            f"rejected={result.rejected} skipped={result.skipped_duplicates}"
        )

    report = run_category_audit(context.store, registry)

    assert report["issues"]["registered_missing_in_db"] == []
    assert report["issues"]["unregistered_in_db"] == []
    assert report["issues"]["alias_only"] == []
    assert report["needs_maintenance"] is False
