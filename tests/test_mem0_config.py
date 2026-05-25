from __future__ import annotations

from event_maintainer.config import AppSettings
from event_maintainer.memory.mem0_store import (
    build_default_mem0_config,
    normalize_mem0_config,
)


def test_build_default_mem0_config_uses_openai_base_url() -> None:
    cfg = build_default_mem0_config(AppSettings())
    assert "base_url" not in cfg["llm"]["config"]
    assert "base_url" not in cfg["embedder"]["config"]
    assert cfg["llm"]["config"]["openai_base_url"]
    assert cfg["embedder"]["config"]["openai_base_url"]


def test_normalize_mem0_config_maps_legacy_base_url() -> None:
    raw = {
        "llm": {"provider": "openai", "config": {"model": "m", "base_url": "https://llm"}},
        "embedder": {
            "provider": "openai",
            "config": {"model": "e", "base_url": "https://embed"},
        },
    }
    cfg = normalize_mem0_config(raw)
    assert cfg["llm"]["config"]["openai_base_url"] == "https://llm"
    assert "base_url" not in cfg["llm"]["config"]
    assert cfg["embedder"]["config"]["openai_base_url"] == "https://embed"
