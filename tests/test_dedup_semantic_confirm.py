from __future__ import annotations

from event_maintainer.dedup.service import DedupService
from event_maintainer.memory import MemorySearchResult


def test_confirm_rejects_when_linked_event_missing() -> None:
    class _Store:
        def get_event(self, event_id: str) -> None:
            return None

    svc = DedupService(_Store(), None, 0.85, semantic_text_confirm_ratio=0.75)
    result = MemorySearchResult(memory="title: other", score=1.0, event_id="gone-id")
    assert not svc._confirm_semantic_duplicate("title: jobless claims", result)


def test_confirm_accepts_high_text_overlap() -> None:
    text = "title: Fed\nsource: FOMC\ntime: 2026-05-18\nsummary: hold rates"
    svc = DedupService(None, None, 0.85, semantic_text_confirm_ratio=0.75)
    result = MemorySearchResult(memory=text, score=0.99, event_id=None)
    assert svc._confirm_semantic_duplicate(text, result)
