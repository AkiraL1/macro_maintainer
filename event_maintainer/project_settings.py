"""Load/save project settings.json (GUI + unattended schedule SSOT)."""
from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

_SETTINGS_ENV = "EVENT_MAINTAINER_SETTINGS"
_ENV_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=(.*)$")


def settings_path(project_root: Path | None = None) -> Path:
    raw = os.getenv(_SETTINGS_ENV, "./settings.json")
    path = Path(raw)
    if path.is_absolute():
        return path
    root = project_root or Path.cwd()
    return root / path


def default_settings() -> dict[str, Any]:
    return {
        "database": {"path": "./macro_maintainer.sqlite3"},
        "mem0": {
            "enabled": False,
            "dup_threshold": 0.85,
            "ttl_days": 30,
            "prune_on_start": True,
            "infer_on_add": False,
        },
        "maintenance": {"past_hours": 72, "future_days": 7},
        "unattended": {
            "enabled": False,
            "task_name": "MacroMaintainer-UpdateDatabase",
            "daily_at": "08:00",
            "every_minutes": 0,
        },
    }


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overlay.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_settings(project_root: Path | None = None) -> dict[str, Any]:
    path = settings_path(project_root)
    if not path.is_file():
        return default_settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return default_settings()
    if not isinstance(raw, dict):
        return default_settings()
    return deep_merge(default_settings(), raw)


def save_settings(data: dict[str, Any], project_root: Path | None = None) -> Path:
    path = settings_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    merged = deep_merge(default_settings(), data)
    path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def get_nested(data: dict[str, Any], dotted: str, default: Any = None) -> Any:
    current: Any = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


def maintenance_past_hours_from_settings(project_root: Path | None = None) -> int:
    value = get_nested(load_settings(project_root), "maintenance.past_hours", 72)
    return int(value)


def maintenance_future_days_from_settings(project_root: Path | None = None) -> int:
    value = get_nested(load_settings(project_root), "maintenance.future_days", 7)
    return int(value)


def settings_to_env_updates(data: dict[str, Any]) -> dict[str, str]:
    return {
        "EVENT_DB_PATH": str(get_nested(data, "database.path", "./macro_maintainer.sqlite3")),
        "MEM0_ENABLED": "true" if get_nested(data, "mem0.enabled", False) else "false",
        "MAINTENANCE_PAST_HOURS": str(int(get_nested(data, "maintenance.past_hours", 72))),
        "MAINTENANCE_FUTURE_DAYS": str(int(get_nested(data, "maintenance.future_days", 7))),
    }


def sync_dotenv(project_root: Path, updates: dict[str, str]) -> None:
    env_path = project_root / ".env"
    lines: list[str] = []
    if env_path.is_file():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        match = _ENV_LINE.match(stripped)
        if not match:
            new_lines.append(line)
            continue
        key = match.group(1)
        if key in updates:
            new_lines.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            new_lines.append(line)

    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
