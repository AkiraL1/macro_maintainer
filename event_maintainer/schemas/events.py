from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from event_maintainer.schemas.categories import normalize_categories, primary_category


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class KeyMetricDraft:
    id: str | None = None
    name: str = ""
    value: str = ""
    previous_value: str | None = None
    change: float | None = None
    unit: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "value": self.value,
            "previous_value": self.previous_value,
            "change": self.change,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class EventDraft:
    title: str
    source: str
    event_time: str
    raw_content: str
    summary: str = ""
    content: str = ""
    country: str = ""
    category: str = ""
    categories: tuple[str, ...] = ()
    importance_score: float = 0.0
    impact_score: float = 0.0
    symbols: tuple[str, ...] = ()
    analysis: str = ""
    end_time: str | None = None
    key_metrics: tuple[KeyMetricDraft, ...] = ()
    related_event_ids: tuple[str, ...] = ()
    extras: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        normalized = normalize_categories(
            categories=self.categories,
            legacy_category=self.category,
        )
        object.__setattr__(self, "categories", normalized)
        object.__setattr__(self, "category", primary_category(normalized))

    def dedup_hash(self) -> str:
        payload = {
            "title": self.title.strip().lower(),
            "source": self.source.strip().lower(),
            "event_time": self.event_time.strip(),
            "raw_content": self.raw_content.strip(),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def fingerprint(self) -> str:
        return self.dedup_hash()

    def memory_text(self) -> str:
        parts = [
            f"title: {self.title}",
            f"source: {self.source}",
            f"time: {self.event_time}",
            f"categories: {', '.join(self.categories)}",
            f"summary: {self.summary or self.raw_content}",
        ]
        return "\n".join(part for part in parts if part.split(": ", 1)[1])


@dataclass(frozen=True)
class StoredEvent:
    id: str
    draft: EventDraft
    dedup_hash: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class DedupDecision:
    is_duplicate: bool
    reason: str
    duplicate_event_id: str | None = None
    score: float = 0.0


@dataclass(frozen=True)
class MaintenanceResult:
    inserted: int = 0
    skipped_duplicates: int = 0
    needs_completion: int = 0
    rejected: int = 0
    log_ids: tuple[int, ...] = ()
