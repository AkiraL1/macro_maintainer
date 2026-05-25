from __future__ import annotations

from pathlib import Path

from event_maintainer.project_settings import (
    default_settings,
    load_settings,
    save_settings,
    settings_to_env_updates,
    sync_dotenv,
)
from event_maintainer.gui.settings_form import form_to_settings as gui_form_to_settings


def test_default_unattended_disabled():
    data = default_settings()
    assert data["unattended"]["enabled"] is False


def test_save_and_load_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = default_settings()
    payload["unattended"]["enabled"] = True
    save_settings(payload, tmp_path)
    loaded = load_settings(tmp_path)
    assert loaded["unattended"]["enabled"] is True


def test_sync_dotenv_updates_keys(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("EVENT_DB_PATH=./old.sqlite3\nMEM0_ENABLED=false\n", encoding="utf-8")
    updates = settings_to_env_updates(default_settings())
    updates["EVENT_DB_PATH"] = "./new.sqlite3"
    sync_dotenv(tmp_path, updates)
    text = env.read_text(encoding="utf-8")
    assert "EVENT_DB_PATH=./new.sqlite3" in text
    assert "MAINTENANCE_PAST_HOURS=72" in text


def test_gui_form_validation():
    data, err = gui_form_to_settings(
        db_path="./db.sqlite3",
        mem0_enabled=True,
        dup_threshold="0.85",
        past_hours="72",
        future_days="7",
        unattended_enabled=False,
        daily_at="09:00",
        every_minutes="0",
        task_name="MacroMaintainer-UpdateDatabase",
    )
    assert err is None
    assert data is not None
    assert data["unattended"]["enabled"] is False
