from __future__ import annotations

from pathlib import Path

from event_maintainer.project_settings import (
    default_settings,
    load_settings,
    save_settings,
    settings_to_env_updates,
    sync_dotenv,
)


def test_default_settings_shape():
    data = default_settings()
    assert "database" in data
    assert "maintenance" in data
    assert "unattended" not in data


def test_save_and_load_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = default_settings()
    payload["maintenance"]["past_hours"] = 48
    save_settings(payload, tmp_path)
    loaded = load_settings(tmp_path)
    assert loaded["maintenance"]["past_hours"] == 48


def test_sync_dotenv_updates_keys(tmp_path: Path):
    env = tmp_path / ".env"
    env.write_text("EVENT_DB_PATH=./old.sqlite3\nMEM0_ENABLED=false\n", encoding="utf-8")
    updates = settings_to_env_updates(default_settings())
    updates["EVENT_DB_PATH"] = "./new.sqlite3"
    sync_dotenv(tmp_path, updates)
    text = env.read_text(encoding="utf-8")
    assert "EVENT_DB_PATH=./new.sqlite3" in text
    assert "MAINTENANCE_PAST_HOURS=72" in text
