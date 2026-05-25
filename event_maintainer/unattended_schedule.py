"""Sync Windows scheduled task with settings.json unattended.enabled."""
from __future__ import annotations

import subprocess
from pathlib import Path

from event_maintainer.gui.encoding_utils import build_subprocess_env, powershell_command
from event_maintainer.project_settings import get_nested, load_settings


def apply_unattended_schedule(project_root: Path, settings: dict | None = None) -> tuple[bool, str]:
    data = settings if settings is not None else load_settings(project_root)
    script = project_root / "scripts" / "register-scheduled-task.ps1"
    if not script.is_file():
        return False, f"未找到脚本: {script}"

    enabled = bool(get_nested(data, "unattended.enabled", False))
    task_name = str(get_nested(data, "unattended.task_name", "MacroMaintainer-UpdateDatabase"))

    if not enabled:
        extra = ("-Unregister", "-TaskName", task_name)
        cmd = powershell_command(str(script), str(project_root), extra)
        return _run(cmd, project_root, "已关闭无人值守计划任务")

    daily_at = str(get_nested(data, "unattended.daily_at", "08:00"))
    every_minutes = int(get_nested(data, "unattended.every_minutes", 0))
    if every_minutes > 0:
        extra = ("-EveryMinutes", str(every_minutes), "-TaskName", task_name)
    else:
        extra = ("-At", daily_at, "-TaskName", task_name)

    cmd = powershell_command(str(script), str(project_root), extra)
    return _run(cmd, project_root, "已注册无人值守计划任务")


def ensure_unattended_schedule(project_root: Path) -> tuple[bool, str]:
    """Apply settings.json to Task Scheduler (call on GUI startup)."""
    return apply_unattended_schedule(project_root)


def _run(cmd: list[str], project_root: Path, ok_message: str) -> tuple[bool, str]:
    env = build_subprocess_env()
    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            env=env,
            capture_output=True,
            timeout=120,
        )
    except Exception as exc:
        return False, str(exc)

    out = (result.stdout or b"") + (result.stderr or b"")
    text = out.decode("utf-8", errors="replace").strip()
    if result.returncode != 0:
        return False, text or f"退出码 {result.returncode}"
    return True, text or ok_message
