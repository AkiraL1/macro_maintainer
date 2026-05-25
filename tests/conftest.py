from __future__ import annotations

import os
from pathlib import Path

import pytest

_REGISTRY = """---
description: test registry
categories:
  - label: 央行
    aliases: [monetary_policy, central_bank]
  - label: 宏观
    aliases: [macro]
  - label: 经济
    aliases: [labor_market, economy]
  - label: 加密货币
    aliases: [crypto]
---
"""


@pytest.fixture
def category_registry_file(tmp_path: Path) -> Path:
    path = tmp_path / "event_category.mdc"
    path.write_text(_REGISTRY, encoding="utf-8")
    return path


@pytest.fixture
def category_registry_env(category_registry_file: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("EVENT_CATEGORY_REGISTRY", str(category_registry_file))
