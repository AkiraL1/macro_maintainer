"""Settings tab: edit and save settings.json + sync .env."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

import customtkinter as ctk
from dotenv import load_dotenv

from event_maintainer.gui.schedule_apply import apply_unattended_schedule
from event_maintainer.gui.settings_form import form_to_settings
from event_maintainer.project_settings import (
    get_nested,
    load_settings,
    save_settings,
    settings_to_env_updates,
    sync_dotenv,
)


class SettingsView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        project_root: Path,
        on_saved: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.project_root = project_root
        self.on_saved = on_saved
        self._data = load_settings(project_root)
        self._build()
        self._load_form()

    def _build(self) -> None:
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=12, pady=(12, 4))

        ctk.CTkButton(
            toolbar,
            text="保存设置",
            width=120,
            command=self._save,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            toolbar,
            text="重新加载",
            width=100,
            command=self._reload,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            toolbar,
            text="打开项目目录",
            width=120,
            command=self._open_project_dir,
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            toolbar,
            text="打开 .env",
            width=100,
            command=self._open_dotenv,
        ).pack(side="left")

        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=12, pady=8)

        self._section(scroll, "数据库")
        self.db_path = self._row_entry(scroll, "数据库路径 (database.path)", 420)

        self._section(scroll, "Mem0 语义去重")
        self.mem0_switch = ctk.CTkSwitch(scroll, text="启用 Mem0 (mem0.enabled)")
        self.mem0_switch.pack(anchor="w", padx=12, pady=4)
        self.dup_threshold = self._row_entry(scroll, "去重阈值 (0–1)", 120)

        self._section(scroll, "维护时间窗")
        self.past_hours = self._row_entry(scroll, "过去 N 小时 (past_hours)", 100)
        self.future_days = self._row_entry(scroll, "未来 N 天 (future_days)", 100)

        self._section(scroll, "无人值守（Windows 计划任务）")
        self.unattended_switch = ctk.CTkSwitch(
            scroll,
            text="启用定时维护 (unattended.enabled，默认关闭)",
        )
        self.unattended_switch.pack(anchor="w", padx=12, pady=4)
        self.task_name = self._row_entry(scroll, "任务名称", 280)
        self.daily_at = self._row_entry(scroll, "每日运行时刻 (HH:mm，every_minutes=0 时)", 120)
        self.every_minutes = self._row_entry(
            scroll, "重复间隔（分钟，>0 则按间隔而非每日）", 120
        )

        ctk.CTkLabel(
            scroll,
            text="API 密钥等敏感项仍在 .env 中配置（保存时会同步 EVENT_DB_PATH / MEM0_ENABLED / 时间窗）。",
            text_color="gray",
            wraplength=520,
            justify="left",
        ).pack(fill="x", padx=12, pady=(8, 4))

        self.status = ctk.CTkLabel(scroll, text="", anchor="w", justify="left")
        self.status.pack(fill="x", padx=12, pady=(4, 12))

    def _section(self, parent: ctk.CTkScrollableFrame, title: str) -> None:
        ctk.CTkLabel(
            parent,
            text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
            anchor="w",
        ).pack(fill="x", pady=(12, 6))

    def _row_entry(
        self, parent: ctk.CTkScrollableFrame, label: str, width: int
    ) -> ctk.CTkEntry:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)
        ctk.CTkLabel(row, text=label, width=280, anchor="w").pack(
            side="left", padx=(12, 8)
        )
        entry = ctk.CTkEntry(row, width=width)
        entry.pack(side="left", padx=(0, 12), pady=4)
        return entry

    def _load_form(self) -> None:
        self._data = load_settings(self.project_root)
        self.db_path.delete(0, "end")
        self.db_path.insert(0, str(get_nested(self._data, "database.path", "")))

        if get_nested(self._data, "mem0.enabled", False):
            self.mem0_switch.select()
        else:
            self.mem0_switch.deselect()

        self.dup_threshold.delete(0, "end")
        self.dup_threshold.insert(0, str(get_nested(self._data, "mem0.dup_threshold", 0.85)))

        self.past_hours.delete(0, "end")
        self.past_hours.insert(0, str(get_nested(self._data, "maintenance.past_hours", 72)))
        self.future_days.delete(0, "end")
        self.future_days.insert(0, str(get_nested(self._data, "maintenance.future_days", 7)))

        if get_nested(self._data, "unattended.enabled", False):
            self.unattended_switch.select()
        else:
            self.unattended_switch.deselect()

        self.task_name.delete(0, "end")
        self.task_name.insert(
            0, str(get_nested(self._data, "unattended.task_name", "MacroMaintainer-UpdateDatabase"))
        )
        self.daily_at.delete(0, "end")
        self.daily_at.insert(0, str(get_nested(self._data, "unattended.daily_at", "08:00")))
        self.every_minutes.delete(0, "end")
        self.every_minutes.insert(0, str(get_nested(self._data, "unattended.every_minutes", 0)))

        self.status.configure(text=f"已加载 {self.project_root / 'settings.json'}")

    def _reload(self) -> None:
        load_dotenv(self.project_root / ".env", override=True)
        self._load_form()

    def _save(self) -> None:
        data, err = form_to_settings(
            db_path=self.db_path.get(),
            mem0_enabled=bool(self.mem0_switch.get()),
            dup_threshold=self.dup_threshold.get(),
            past_hours=self.past_hours.get(),
            future_days=self.future_days.get(),
            unattended_enabled=bool(self.unattended_switch.get()),
            daily_at=self.daily_at.get(),
            every_minutes=self.every_minutes.get(),
            task_name=self.task_name.get(),
            base=self._data,
        )
        if err or data is None:
            self.status.configure(text=err or "保存失败", text_color="#E74C3C")
            return

        path = save_settings(data, self.project_root)
        sync_dotenv(self.project_root, settings_to_env_updates(data))
        load_dotenv(self.project_root / ".env", override=True)

        ok, msg = apply_unattended_schedule(self.project_root, data)
        if ok:
            self.status.configure(
                text=f"已保存 {path.name}，已同步 .env。计划任务: {msg}",
                text_color=("gray10", "gray90"),
            )
        else:
            self.status.configure(
                text=f"已保存 {path.name}，但计划任务: {msg}",
                text_color="#E67E22",
            )

        self._data = data
        if self.on_saved:
            self.on_saved()

    def _open_project_dir(self) -> None:
        os.startfile(self.project_root)  # type: ignore[attr-defined]

    def _open_dotenv(self) -> None:
        path = self.project_root / ".env"
        if not path.is_file():
            path = self.project_root / ".env.example"
        if path.is_file():
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["explorer.exe", str(self.project_root)], check=False)
