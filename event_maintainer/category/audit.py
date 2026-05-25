from __future__ import annotations

from typing import Any

from event_maintainer.category.registry import CategoryRegistry
from event_maintainer.db import SQLiteEventStore


def run_category_audit(
    store: SQLiteEventStore, registry: CategoryRegistry
) -> dict[str, Any]:
    counts = store.category_counts()
    registered = sorted(registry.labels)
    alias_map = registry.alias_to_label()

    empty: list[str] = []
    alias_only: list[dict[str, str]] = []
    unregistered_in_db: list[dict[str, str]] = []

    for event in store.list_events():
        labels = list(event.draft.categories)
        if not labels:
            empty.append(event.id)
            continue
        for label in labels:
            if registry.is_registered_label(label):
                continue
            if label in alias_map:
                alias_only.append(
                    {
                        "id": event.id,
                        "category": label,
                        "suggest": alias_map[label],
                    }
                )
                continue
            unregistered_in_db.append({"id": event.id, "category": label})

    registered_missing_in_db = [
        label for label in registered if counts.get(label, 0) == 0
    ]
    issues = {
        "registered_missing_in_db": registered_missing_in_db,
        "unregistered_in_db": unregistered_in_db,
        "empty": empty,
        "alias_only": alias_only,
    }
    needs_maintenance = any(issues.values())
    return {
        "registry_path": str(registry.path),
        "registered": registered,
        "counts": counts,
        "issues": issues,
        "needs_maintenance": needs_maintenance,
    }
