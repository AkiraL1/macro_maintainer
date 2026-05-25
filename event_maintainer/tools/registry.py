from __future__ import annotations

from dataclasses import asdict

from event_maintainer.category import load_registry, run_category_audit
from event_maintainer.db import SQLiteEventStore, parse_event_time
from event_maintainer.dedup import DedupService
from event_maintainer.maintenance import MaintenanceService
from event_maintainer.recency import (
    classify_event_time,
    maintenance_window,
    window_payload,
)
from event_maintainer.schemas import EventDraft


class ToolRegistry:
    def __init__(
        self,
        store: SQLiteEventStore,
        dedup: DedupService,
        maintenance: MaintenanceService,
    ) -> None:
        self.store = store
        self.dedup = dedup
        self.maintenance = maintenance

    def search_events(
        self,
        *,
        past_hours: int | None = None,
        future_days: int | None = None,
        use_maintenance_window: bool = False,
    ) -> list[dict[str, object]]:
        if not use_maintenance_window and past_hours is None and future_days is None:
            return [
                self.store._stored_to_api_dict(event)
                for event in self.store.list_events()
            ]
        start, end, ref = maintenance_window(
            past_hours=past_hours, future_days=future_days
        )
        events, _ = self.store.list_events_in_time_window(start, end)
        rows: list[dict[str, object]] = []
        for event in events:
            row = self.store._stored_to_api_dict(event)
            event_time = parse_event_time(event.draft.event_time)
            row["recency_phase"] = classify_event_time(
                event_time,
                now=ref,
                past_hours=past_hours,
                future_days=future_days,
            )
            rows.append(row)
        return rows

    def recency_window(self) -> dict[str, object]:
        return window_payload()

    def recency_audit(
        self,
        *,
        past_hours: int | None = None,
        future_days: int | None = None,
    ) -> dict[str, object]:
        start, end, ref = maintenance_window(
            past_hours=past_hours, future_days=future_days
        )
        in_window, in_total = self.store.list_events_in_time_window(start, end)
        all_events = self.store.list_events()
        in_ids = {event.id for event in in_window}
        recent: list[dict[str, object]] = []
        upcoming: list[dict[str, object]] = []
        outside: list[dict[str, object]] = []
        for event in in_window:
            event_time = parse_event_time(event.draft.event_time)
            phase = classify_event_time(
                event_time, now=ref, past_hours=past_hours, future_days=future_days
            )
            brief = {
                "id": event.id,
                "title": event.draft.title,
                "event_time": event.draft.event_time,
                "category": event.draft.category,
                "recency_phase": phase,
            }
            if phase == "recent":
                recent.append(brief)
            else:
                upcoming.append(brief)
        for event in all_events:
            if event.id in in_ids:
                continue
            outside.append(
                {
                    "id": event.id,
                    "title": event.draft.title,
                    "event_time": event.draft.event_time,
                    "category": event.draft.category,
                    "recency_phase": "outside",
                }
            )
        payload = window_payload(now=ref, past_hours=past_hours, future_days=future_days)
        payload["in_window_count"] = in_total
        payload["recent_count"] = len(recent)
        payload["upcoming_count"] = len(upcoming)
        payload["outside_window_count"] = len(outside)
        payload["recent"] = recent
        payload["upcoming"] = upcoming
        payload["outside_window"] = outside
        return payload

    def init_database(self) -> dict[str, object]:
        self.store.initialize()
        return self.store.database_status()

    def database_status(self) -> dict[str, object]:
        return self.store.database_status()

    def get_event(self, event_id: str) -> dict[str, object] | None:
        event = self.store.get_event(event_id)
        return self.store._stored_to_api_dict(event) if event else None

    def list_duplicate_records(self) -> list[dict[str, object]]:
        return self.store.list_duplicate_records()

    def list_maintenance_logs(self) -> list[dict[str, object]]:
        return self.store.list_maintenance_logs()

    def find_possible_duplicates(self, draft: EventDraft) -> dict[str, object]:
        return asdict(self.dedup.check_duplicate(draft))

    def upsert_event(self, draft: EventDraft) -> dict[str, object]:
        result = self.maintenance.ingest_events([draft])
        return asdict(result)

    def record_maintenance_log(
        self,
        action: str,
        status: str,
        detail: str,
        event_id: str | None = None,
    ) -> int:
        return self.store.record_log(action, status, detail, event_id)

    def category_audit(self) -> dict[str, object]:
        registry = load_registry(self.maintenance._category_registry_path)
        return run_category_audit(self.store, registry)

    def update_event(
        self,
        event_id: str,
        *,
        category: str | None = None,
        categories: tuple[str, ...] | None = None,
        summary: str | None = None,
        country: str | None = None,
    ) -> dict[str, object]:
        return self.maintenance.update_event(
            event_id,
            category=category,
            categories=categories,
            summary=summary,
            country=country,
        )
