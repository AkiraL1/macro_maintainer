from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from event_maintainer.schemas import EventDraft, KeyMetricDraft
from event_maintainer.schemas.categories import normalize_categories


def load_event_drafts(path: Path) -> list[EventDraft]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("event input must be a JSON list")
    return [_draft_from_mapping(item) for item in payload]


def _draft_from_mapping(item: Any) -> EventDraft:
    if not isinstance(item, dict):
        raise ValueError("each event input item must be an object")
    metrics = tuple(
        KeyMetricDraft(
            id=m.get("id"),
            name=str(m.get("name", "")),
            value=str(m.get("value", "")),
            previous_value=m.get("previous_value"),
            change=m.get("change"),
            unit=m.get("unit"),
        )
        for m in item.get("key_metrics", [])
        if isinstance(m, dict)
    )
    raw_categories = item.get("categories")
    if raw_categories is not None:
        if not isinstance(raw_categories, list):
            raise ValueError("categories must be a JSON array of registered labels")
        categories = normalize_categories(
            categories=tuple(str(label) for label in raw_categories)
        )
        legacy_category = ""
    else:
        categories = ()
        legacy_category = str(item.get("category", ""))
    return EventDraft(
        title=str(item["title"]),
        source=str(item["source"]),
        event_time=str(item["event_time"]),
        raw_content=str(item["raw_content"]),
        summary=str(item.get("summary", "")),
        content=str(item.get("content", "")),
        country=str(item.get("country", "")),
        category=legacy_category,
        categories=categories,
        importance_score=float(item.get("importance_score", 0.0)),
        impact_score=float(item.get("impact_score", 0.0)),
        symbols=tuple(str(symbol) for symbol in item.get("symbols", ())),
        analysis=str(item.get("analysis", "")),
        end_time=item.get("end_time"),
        key_metrics=metrics,
        related_event_ids=tuple(str(rid) for rid in item.get("related_event_ids", ())),
        extras=dict(item.get("extras", {})),
    )
