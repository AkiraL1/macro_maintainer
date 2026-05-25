from __future__ import annotations

from event_maintainer.memory import l2_distance_to_similarity


def test_l2_distance_to_similarity_monotonic() -> None:
    close = l2_distance_to_similarity(0.115)
    far = l2_distance_to_similarity(1.178)
    assert close > far
    assert close > 0.85
    assert far < 0.85
