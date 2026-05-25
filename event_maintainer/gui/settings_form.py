"""Build settings dict from GUI fields and validate."""
from __future__ import annotations

from typing import Any

from event_maintainer.project_settings import deep_merge, default_settings


def form_to_settings(
    *,
    db_path: str,
    mem0_enabled: bool,
    dup_threshold: str,
    past_hours: str,
    future_days: str,
    unattended_enabled: bool,
    daily_at: str,
    every_minutes: str,
    task_name: str,
    base: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        past = int(past_hours.strip())
        future = int(future_days.strip())
        dup = float(dup_threshold.strip())
        every = int(every_minutes.strip() or "0")
    except ValueError as exc:
        return None, f"数值格式无效: {exc}"

    if past < 1 or future < 1:
        return None, "维护时间窗须为正整数"
    if not 0.0 < dup <= 1.0:
        return None, "Mem0 去重阈值须在 (0, 1] 之间"
    if every < 0:
        return None, "重复间隔分钟数不能为负"

    data = deep_merge(default_settings(), base or {})
    mem0_block = data.get("mem0")
    if not isinstance(mem0_block, dict):
        mem0_block = {}
    unattended_block = data.get("unattended")
    if not isinstance(unattended_block, dict):
        unattended_block = {}

    data["database"] = {"path": db_path.strip() or "./macro_maintainer.sqlite3"}
    data["mem0"] = {**mem0_block, "enabled": mem0_enabled, "dup_threshold": dup}
    data["maintenance"] = {"past_hours": past, "future_days": future}
    data["unattended"] = {
        **unattended_block,
        "enabled": unattended_enabled,
        "daily_at": daily_at.strip() or "08:00",
        "every_minutes": every,
        "task_name": task_name.strip() or "MacroMaintainer-UpdateDatabase",
    }
    return data, None
