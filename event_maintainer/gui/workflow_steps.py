"""Workflow step definitions (SSOT for maintenance GUI)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

WorkflowId = Literal["interactive", "unattended"]


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    title: str
    description: str
    doc_path: str | None = None
    cli_command: str | None = None
    ps_script: str | None = None
    runnable: bool = True
    requires_confirm: bool = False


INTERACTIVE_STEPS: tuple[WorkflowStep, ...] = (
    WorkflowStep(
        id="category_audit",
        title="分类审计",
        description="category-audit：校验 events 分类与 event_category.mdc 注册表。",
        doc_path=".cursor/rules/event_category.mdc",
        cli_command="category-audit",
    ),
    WorkflowStep(
        id="recency_window",
        title="时效窗口",
        description="recency-window：输出维护时间窗（默认过去 72h + 未来 7d）与检索提示。",
        cli_command="recency-window",
    ),
    WorkflowStep(
        id="recency_audit",
        title="时效审计",
        description="recency-audit：将库内事件分为 recent / upcoming / outside_window。",
        cli_command="recency-audit",
    ),
    WorkflowStep(
        id="search_web",
        title="联网检索",
        description="在 Cursor 中使用 search-web --query \"...\"；GUI 不自动执行（需查询词）。",
        doc_path=".cursor/skills/maintain-events/SKILL.md",
        runnable=False,
    ),
    WorkflowStep(
        id="ingest",
        title="草稿入库",
        description="编写 drafts.json 后：python -m event_maintainer.main ingest --input <file>。",
        doc_path=".cursor/rules/事件入库去重规则.mdc",
        runnable=False,
    ),
    WorkflowStep(
        id="list_duplicates",
        title="重复记录",
        description="list-duplicates：查看 ingest 跳过的 dedup_hash_match / mem0_semantic_match。",
        cli_command="list-duplicates",
    ),
    WorkflowStep(
        id="list_logs",
        title="维护日志",
        description="list-logs：查看 ingest / update-event 等维护操作记录。",
        cli_command="list-logs",
    ),
    WorkflowStep(
        id="db_status",
        title="库状态",
        description="db-status：三表行数与库路径概览。",
        cli_command="db-status",
    ),
)

UNATTENDED_STEPS: tuple[WorkflowStep, ...] = (
    WorkflowStep(
        id="prerequisites",
        title="前置条件",
        description="agent 在 PATH 且已 agent login；pip install -e \".[dev]\"（可选 .[mem0]）。",
        doc_path=".cursor/skills/maintain-events/SKILL.md",
        runnable=False,
    ),
    WorkflowStep(
        id="run_maintain_agent",
        title="运行维护 Agent",
        description="run-maintain-agent.ps1：无头 agent -p，日志写入 scripts/logs/。",
        ps_script="scripts/run-maintain-agent.ps1",
    ),
    WorkflowStep(
        id="view_logs",
        title="查看日志",
        description="可读 maintain-<timestamp>.log 与 .jsonl（stream-json）。",
        doc_path="scripts/logs/",
        runnable=False,
    ),
    WorkflowStep(
        id="register_task",
        title="注册计划任务",
        description="建议在「项目设置」页保存并启用 unattended.enabled；亦可手动运行 register-scheduled-task.ps1。",
        ps_script="scripts/register-scheduled-task.ps1",
        requires_confirm=True,
    ),
)

WORKFLOWS: dict[WorkflowId, tuple[WorkflowStep, ...]] = {
    "interactive": INTERACTIVE_STEPS,
    "unattended": UNATTENDED_STEPS,
}
