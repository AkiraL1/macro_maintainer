"""Read-only settings rows for the GUI (testable without Tk)."""
from __future__ import annotations

import os
import re
from dataclasses import asdict
from pathlib import Path

from event_maintainer.config import AppSettings
from event_maintainer.recency import (
    FUTURE_DAYS_DEFAULT,
    PAST_HOURS_DEFAULT,
    maintenance_future_days,
    maintenance_past_hours,
)

_SENSITIVE_PATTERN = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD)", re.IGNORECASE)
_ENV_KEY_PATTERN = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=")


def project_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_env_example_keys(path: Path) -> list[str]:
    if not path.is_file():
        return []
    keys: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _ENV_KEY_PATTERN.match(stripped)
        if match:
            keys.append(match.group(1))
    return keys


def is_sensitive_env_key(key: str) -> bool:
    return bool(_SENSITIVE_PATTERN.search(key))


def mask_env_display(key: str, value: str | None) -> str:
    if not value:
        return "（未设置）"
    if is_sensitive_env_key(key):
        return "***（已设置）"
    return value


def format_settings_value(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def app_settings_rows() -> list[tuple[str, str]]:
    settings = AppSettings()
    rows: list[tuple[str, str]] = []
    for key, value in sorted(asdict(settings).items()):
        rows.append((f"settings.{key}", format_settings_value(value)))
    return rows


def env_rows(env_example_path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for key in parse_env_example_keys(env_example_path):
        rows.append((key, mask_env_display(key, os.getenv(key))))
    return rows


def maintenance_window_rows() -> list[tuple[str, str]]:
    return [
        (
            "MAINTENANCE_PAST_HOURS",
            str(maintenance_past_hours())
            + ("" if os.getenv("MAINTENANCE_PAST_HOURS", "").strip() else f" (默认 {PAST_HOURS_DEFAULT})"),
        ),
        (
            "MAINTENANCE_FUTURE_DAYS",
            str(maintenance_future_days())
            + (
                ""
                if os.getenv("MAINTENANCE_FUTURE_DAYS", "").strip()
                else f" (默认 {FUTURE_DAYS_DEFAULT})"
            ),
        ),
    ]
