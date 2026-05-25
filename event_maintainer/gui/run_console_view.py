"""Run tab: quick actions and shared log output."""
from __future__ import annotations

import sys
from typing import Callable

import customtkinter as ctk

from event_maintainer.gui.process_runner import ProcessRunner, RunJob, cli_job, ps_job


class RunConsoleView(ctk.CTkFrame):
    QUICK_JOBS: tuple[tuple[str, RunJob], ...] = (
        ("初始化数据库", cli_job("init-db", "init-db")),
        ("库状态", cli_job("db-status")),
        ("分类审计", cli_job("category-audit")),
        ("时效窗口", cli_job("recency-window")),
        ("时效审计", cli_job("recency-audit")),
        (
            "运行维护 Agent",
            ps_job("scripts/run-maintain-agent.ps1", "run-maintain-agent"),
        ),
    )

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        runner: ProcessRunner,
        agent_available: bool,
        on_run: Callable[[RunJob], None],
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.runner = runner
        self.agent_available = agent_available
        self.on_run = on_run
        self._buttons: list[ctk.CTkButton] = []
        self._build()

    def _build(self) -> None:
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=(12, 4))

        for label, job in self.QUICK_JOBS:
            disabled = label == "运行维护 Agent" and not self.agent_available
            btn = ctk.CTkButton(
                bar,
                text=label,
                height=32,
                corner_radius=8,
                state="disabled" if disabled else "normal",
                command=lambda j=job: self.on_run(j),
            )
            btn.pack(side="left", padx=(0, 8), pady=4)
            self._buttons.append(btn)

        log_family = "Microsoft YaHei UI" if sys.platform == "win32" else "Consolas"
        self.log = ctk.CTkTextbox(self, font=ctk.CTkFont(family=log_family, size=12))
        self.log.pack(fill="both", expand=True, padx=12, pady=8)

        self.status = ctk.CTkLabel(self, text="就绪", anchor="w")
        self.status.pack(fill="x", padx=12, pady=(0, 12))

    def append_log(self, text: str) -> None:
        self.log.insert("end", text)
        self.log.see("end")

    def clear_log(self) -> None:
        self.log.delete("1.0", "end")

    def set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def set_buttons_enabled(self, enabled: bool) -> None:
        for btn in self._buttons:
            label = btn.cget("text")
            if label == "运行维护 Agent" and not self.agent_available:
                btn.configure(state="disabled")
            else:
                btn.configure(state="normal" if enabled else "disabled")
