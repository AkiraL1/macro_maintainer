from __future__ import annotations

from difflib import SequenceMatcher

from event_maintainer.db import SQLiteEventStore
from event_maintainer.memory import Mem0MemoryStore, MemorySearchResult
from event_maintainer.schemas import DedupDecision, EventDraft


class DedupService:
    def __init__(
        self,
        store: SQLiteEventStore,
        memory: Mem0MemoryStore,
        semantic_threshold: float,
        *,
        semantic_text_confirm_ratio: float = 0.75,
    ) -> None:
        self.store = store
        self.memory = memory
        self.semantic_threshold = semantic_threshold
        self.semantic_text_confirm_ratio = semantic_text_confirm_ratio

    def check_duplicate(self, draft: EventDraft) -> DedupDecision:
        dedup_hash = draft.dedup_hash()
        exact_match = self.store.find_by_dedup_hash(dedup_hash)
        if exact_match:
            return DedupDecision(
                is_duplicate=True,
                reason="dedup_hash_match",
                duplicate_event_id=exact_match.id,
                score=1.0,
            )

        draft_memory = draft.memory_text()
        for result in self.memory.search_similar_events(draft):
            if result.score < self.semantic_threshold:
                continue
            if not self._confirm_semantic_duplicate(draft_memory, result):
                continue
            return DedupDecision(
                is_duplicate=True,
                reason="mem0_semantic_match",
                duplicate_event_id=result.event_id,
                score=result.score,
            )

        return DedupDecision(is_duplicate=False, reason="new_event")

    def _confirm_semantic_duplicate(
        self, draft_memory: str, result: MemorySearchResult
    ) -> bool:
        """Mem0 vector score alone can false-positive; require text overlap."""
        if result.event_id:
            existing = self.store.get_event(result.event_id)
            if not existing:
                return False
            baseline = existing.draft.memory_text()
        else:
            baseline = result.memory
        if not baseline.strip():
            return False
        ratio = SequenceMatcher(None, draft_memory, baseline).ratio()
        return ratio >= self.semantic_text_confirm_ratio
