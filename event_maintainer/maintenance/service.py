from __future__ import annotations

from pathlib import Path

from event_maintainer.category import (
    load_registry,
    validate_categories_for_write,
    validate_category_for_write,
)
from event_maintainer.db import SQLiteEventStore
from event_maintainer.dedup import DedupService
from event_maintainer.memory import Mem0MemoryStore
from event_maintainer.schemas import EventDraft, MaintenanceResult, StoredEvent


class MaintenanceService:
    def __init__(
        self,
        store: SQLiteEventStore,
        dedup: DedupService,
        memory: Mem0MemoryStore,
        category_registry_path: Path | None = None,
    ) -> None:
        self.store = store
        self.dedup = dedup
        self.memory = memory
        self._category_registry_path = category_registry_path

    def _registry(self):
        path = self._category_registry_path
        return load_registry(path) if path else load_registry()

    def ingest_events(self, drafts: list[EventDraft]) -> MaintenanceResult:
        inserted = 0
        skipped = 0
        rejected = 0
        needs_completion = 0
        log_ids: list[int] = []
        registry = self._registry()

        for draft in drafts:
            category_error = validate_categories_for_write(draft.categories, registry)
            if category_error:
                rejected += 1
                log_ids.append(
                    self.store.record_log(
                        action="ingest",
                        status="rejected",
                        detail=category_error,
                        event_id=None,
                    )
                )
                continue

            decision = self.dedup.check_duplicate(draft)
            if decision.is_duplicate:
                skipped += 1
                self.store.record_duplicate(draft.dedup_hash(), decision)
                log_ids.append(
                    self.store.record_log(
                        action="dedup",
                        status="skipped",
                        detail=f"{decision.reason}:{decision.score:.3f}",
                        event_id=decision.duplicate_event_id,
                    )
                )
                continue

            stored = self.store.upsert_event(draft)
            inserted += 1
            self.memory.add_event_memory(stored)
            log_ids.append(
                self.store.record_log(
                    action="upsert_event",
                    status="inserted",
                    detail=stored.draft.title,
                    event_id=stored.id,
                )
            )

            if self._needs_completion(stored):
                needs_completion += 1
                log_ids.append(
                    self.store.record_log(
                        action="field_completion",
                        status="pending",
                        detail="summary/category/country requires review",
                        event_id=stored.id,
                    )
                )

        summary = (
            f"maintenance run inserted={inserted} "
            f"duplicates={skipped} rejected={rejected} "
            f"needs_completion={needs_completion}"
        )
        self.memory.add_run_memory(summary)
        return MaintenanceResult(
            inserted=inserted,
            skipped_duplicates=skipped,
            needs_completion=needs_completion,
            log_ids=tuple(log_ids),
            rejected=rejected,
        )

    def update_event(
        self,
        event_id: str,
        *,
        category: str | None = None,
        categories: tuple[str, ...] | None = None,
        summary: str | None = None,
        country: str | None = None,
    ) -> dict[str, object]:
        registry = self._registry()
        if categories is not None:
            category_error = validate_categories_for_write(categories, registry)
        elif category is not None:
            category_error = validate_category_for_write(category, registry)
        else:
            category_error = None
        if category_error:
            log_id = self.store.record_log(
                action="update_event",
                status="rejected",
                detail=category_error,
                event_id=event_id,
            )
            return {
                "updated": False,
                "event_id": event_id,
                "error": category_error,
                "log_id": log_id,
            }
        if category is None and categories is None and summary is None and country is None:
            return {
                "updated": False,
                "event_id": event_id,
                "error": "no updatable fields provided",
            }
        updated = self.store.update_event_fields(
            event_id,
            category=category,
            categories=categories,
            summary=summary,
            country=country,
        )
        if not updated:
            return {
                "updated": False,
                "event_id": event_id,
                "error": "event not found",
            }
        log_id = self.store.record_log(
            action="update_event",
            status="updated",
            detail=f"categories={list(updated.draft.categories)}",
            event_id=event_id,
        )
        return {
            "updated": True,
            "event_id": event_id,
            "event": self.store._stored_to_api_dict(updated),
            "log_id": log_id,
        }

    @staticmethod
    def _needs_completion(event: StoredEvent) -> bool:
        draft = event.draft
        return not draft.summary or not draft.categories or not draft.country
