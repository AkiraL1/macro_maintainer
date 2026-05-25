"""Main CustomTkinter application."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import customtkinter as ctk
from dotenv import load_dotenv

from event_maintainer.gui.process_runner import ProcessRunner, RunJob
from event_maintainer.gui.run_console_view import RunConsoleView
from event_maintainer.gui.settings_data import project_root_from_module
from event_maintainer.gui.settings_view import SettingsView
from event_maintainer.gui.theme import apply_theme
from event_maintainer.gui.workflow_view import WorkflowView
from event_maintainer.unattended_schedule import ensure_unattended_schedule


def agent_available() -> bool:
    return shutil.which("agent") is not None or shutil.which("cursor-agent") is not None


class MaintainerApp(ctk.CTk):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.runner = ProcessRunner(project_root)
        self._agent_ok = agent_available()

        self.title("Macro Maintainer 控制面板")
        self.geometry("920x640")
        self.minsize(720, 520)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=12, pady=12)

        tab_settings = self.tabview.add("项目设置")
        tab_workflow = self.tabview.add("维护流程")
        tab_run = self.tabview.add("运行与日志")

        SettingsView(tab_settings, self.project_root, on_saved=self._reload_env).pack(
            fill="both", expand=True
        )

        self.console = RunConsoleView(
            tab_run,
            self.runner,
            self._agent_ok,
            on_run=self._start_job,
        )
        self.console.pack(fill="both", expand=True)

        WorkflowView(
            tab_workflow,
            self.project_root,
            self.runner,
            on_run_started=self._on_run_started,
            agent_available=self._agent_ok,
        ).pack(fill="both", expand=True)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(50, self._poll_runner)
        self.after(200, self._sync_unattended_on_startup)

    def _sync_unattended_on_startup(self) -> None:
        ok, msg = ensure_unattended_schedule(self.project_root)
        if not ok:
            self.console.append_log(f"[计划任务同步] {msg}\n")
        elif "Removed" in msg or "关闭" in msg or "disabled" in msg.lower():
            self.console.append_log(f"[计划任务同步] {msg}\n")

    def _reload_env(self) -> None:
        load_dotenv(self.project_root / ".env", override=True)

    def _start_job(self, job: RunJob) -> None:
        if self.runner.run(job):
            self._on_run_started()

    def _on_run_started(self) -> None:
        self.console.clear_log()
        self.console.set_status("运行中…")
        self.console.set_buttons_enabled(False)

    def _poll_runner(self) -> None:
        self.runner.poll_queue(self._handle_event)
        self.after(50, self._poll_runner)

    def _handle_event(self, kind: str, payload: object) -> None:
        if kind == "line":
            self.console.append_log(str(payload))
        elif kind == "started":
            self.console.append_log(f"=== 开始: {payload} ===\n")
        elif kind == "finished":
            code = int(payload)
            self.console.append_log(f"\n=== 结束 (exit {code}) ===\n")
            self.console.set_status(f"完成，退出码 {code}")
            self.console.set_buttons_enabled(True)

    def _on_close(self) -> None:
        self.runner.terminate()
        self.destroy()


def main() -> None:
    try:
        import customtkinter  # noqa: F401
    except ImportError:
        print(
            "缺少 customtkinter。请执行: pip install -e \".[gui]\"",
            file=sys.stderr,
        )
        raise SystemExit(1) from None

    root = project_root_from_module()
    load_dotenv(root / ".env")
    apply_theme()
    app = MaintainerApp(root)
    app.mainloop()
