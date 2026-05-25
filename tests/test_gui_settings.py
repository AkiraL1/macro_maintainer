from __future__ import annotations

from pathlib import Path

from event_maintainer.gui.settings_data import (
    mask_env_display,
    parse_env_example_keys,
    is_sensitive_env_key,
)
from event_maintainer.gui.workflow_steps import INTERACTIVE_STEPS, UNATTENDED_STEPS, WORKFLOWS


def test_mask_sensitive_key():
    assert is_sensitive_env_key("DASHSCOPE_API_KEY")
    assert mask_env_display("DASHSCOPE_API_KEY", "secret") == "***（已设置）"
    assert mask_env_display("DASHSCOPE_API_KEY", None) == "（未设置）"


def test_mask_plain_key():
    assert mask_env_display("EVENT_DB_PATH", "./db.sqlite3") == "./db.sqlite3"
    assert mask_env_display("MEM0_ENABLED", "") == "（未设置）"


def test_parse_env_example_keys(tmp_path: Path):
    example = tmp_path / ".env.example"
    example.write_text(
        "EVENT_DB_PATH=./x.sqlite3\n# comment\nMEM0_ENABLED=true\n",
        encoding="utf-8",
    )
    keys = parse_env_example_keys(example)
    assert keys == ["EVENT_DB_PATH", "MEM0_ENABLED"]


def test_workflow_steps_structure():
    assert len(INTERACTIVE_STEPS) >= 5
    assert len(UNATTENDED_STEPS) >= 3
    assert "interactive" in WORKFLOWS and "unattended" in WORKFLOWS
    runnable = [s for s in INTERACTIVE_STEPS if s.runnable and s.cli_command]
    assert any(s.id == "category_audit" for s in runnable)
