"""Workflow tab: step cards and per-step run buttons."""
from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import Callable

import customtkinter as ctk

from event_maintainer.gui.process_runner import ProcessRunner, RunJob, cli_job, ps_job
from event_maintainer.gui.workflow_steps import (
    UNATTENDED_STEPS,
    INTERACTIVE_STEPS,
    WorkflowId,
    WorkflowStep,
)


class WorkflowView(ctk.CTkFrame):
    def __init__(
        self,
        master: ctk.CTkBaseClass,
        project_root: Path,
        runner: ProcessRunner,
        on_run_started: Callable[[], None],
        agent_available: bool,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self.project_root = project_root
        self.runner = runner
        self.on_run_started = on_run_started
        self.agent_available = agent_available
        self._workflow: WorkflowId = "interactive"
        self._steps_frame: ctk.CTkScrollableFrame | None = None
        self._build()

    def _build(self) -> None:
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(12, 4))

        self._segment = ctk.CTkSegmentedButton(
            top,
            values=["交互式维护", "无人值守"],
            command=self._on_segment,
        )
        self._segment.set("交互式维护")
        self._segment.pack(fill="x")

        self._steps_frame = ctk.CTkScrollableFrame(self)
        self._steps_frame.pack(fill="both", expand=True, padx=12, pady=8)
        self._render_steps()

    def _on_segment(self, value: str) -> None:
        self._workflow = "unattended" if value == "无人值守" else "interactive"
        self._render_steps()

    def _render_steps(self) -> None:
        frame = self._steps_frame
        assert frame is not None
        for child in frame.winfo_children():
            child.destroy()

        steps = INTERACTIVE_STEPS if self._workflow == "interactive" else UNATTENDED_STEPS
        for index, step in enumerate(steps, start=1):
            self._add_step_card(frame, index, step)

    def _add_step_card(self, parent: ctk.CTkScrollableFrame, index: int, step: WorkflowStep) -> None:
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.pack(fill="x", pady=6)

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=12, pady=(10, 4))

        ctk.CTkLabel(
            header,
            text=str(index),
            width=28,
            height=28,
            corner_radius=14,
            fg_color=("#3B8ED0", "#1F6AA5"),
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(
            header,
            text=step.title,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        ctk.CTkLabel(
            card,
            text=step.description,
            anchor="w",
            justify="left",
            wraplength=560,
        ).pack(fill="x", padx=12, pady=(0, 4))

        if step.doc_path:
            ctk.CTkLabel(
                card,
                text=f"文档: {step.doc_path}",
                text_color="gray",
                anchor="w",
            ).pack(fill="x", padx=12, pady=(0, 6))

        if not step.runnable:
            return

        job = self._job_for_step(step)
        if job is None:
            return

        disabled = step.id == "run_maintain_agent" and not self.agent_available
        btn = ctk.CTkButton(
            card,
            text="运行此步",
            height=32,
            corner_radius=8,
            state="disabled" if disabled else "normal",
            command=lambda j=job, s=step: self._run_step(j, s),
        )
        btn.pack(anchor="w", padx=12, pady=(0, 10))
        if disabled:
            ctk.CTkLabel(
                card,
                text="未检测到 agent 命令（请先 agent login）",
                text_color="orange",
                anchor="w",
            ).pack(fill="x", padx=12, pady=(0, 8))

    def _job_for_step(self, step: WorkflowStep) -> RunJob | None:
        if step.cli_command:
            return cli_job(step.cli_command, step.title)
        if step.ps_script:
            return ps_job(step.ps_script, step.title)
        return None

    def _run_step(self, job: RunJob, step: WorkflowStep) -> None:
        if self.runner.is_running:
            return
        if step.requires_confirm:
            ok = messagebox.askyesno(
                "确认",
                "将注册或修改 Windows 计划任务 MacroMaintainer-UpdateDatabase。\n是否继续？",
            )
            if not ok:
                return
        if self.runner.run(job):
            self.on_run_started()
