# OpenClaw 维护编排

本仓库的**写库执行层**仅为 `python -m event_maintainer.main`；**推理与编排**由 [OpenClaw](https://github.com/openclaw/openclaw)（或你本机配置的 OpenClaw 发行版）负责，不再使用 Cursor Agent CLI（`agent`）与本仓库 GUI。

## 分层

| 层 | 职责 |
|----|------|
| OpenClaw | 读规则/技能、联网检索决策、组装 ingest 草稿、调用 Shell |
| `event_maintainer` CLI | 唯一写库路径（ingest、update-event、审计等） |
| `apps/api` | iOS 只读 API |

## OpenClaw 应加载的 SSOT

维护会话开始前，让 OpenClaw 工作区指向**本仓库根目录**，并纳入：

| 路径 | 用途 |
|------|------|
| `scripts/prompts/update-database.txt` | 单次/定时维护提示词 SSOT |
| `.cursor/skills/maintain-events/SKILL.md` | 操作步骤与验证清单 |
| `.cursor/rules/event_category.mdc` | 分类注册表 |
| `.cursor/rules/事件入库去重规则.mdc` | 去重指纹与 ingest 顺序 |
| `.cursor/rules/event_rules.mdc` | 字段边界与维护流程 |
| `.cursor/rules/macro-maintainer.mdc` | 仓库级约束（三表、禁直连 SQL） |

你可把上述路径配置为 OpenClaw 的「项目知识库」或首轮 system 引用；具体配置方式以 OpenClaw 文档为准（本仓库不捆绑 OpenClaw 安装包）。

## 硬性约束（与 `update-database.txt` 一致）

- 所有写库：`python -m event_maintainer.main <子命令>`
- 禁止直接编辑 `*.sqlite3` 或 ad-hoc SQL
- `update-event` 仅可改 `category` / `summary` / `country`（及 `categories`）；禁止改 `title` / `source` / `event_time` / `raw_content`
- ingest 草稿建议写入：`scripts/.runtime/drafts-<yyyyMMdd-HHmmss>.json`（UTF-8 JSON 数组）

## 标准维护命令序列

```powershell
cd <项目根>
pip install -e ".[dev]"   # 可选 ".[mem0]" + .env

python -m event_maintainer.main category-audit
python -m event_maintainer.main recency-window
python -m event_maintainer.main recency-audit
# search-web → 编写 drafts → ingest
python -m event_maintainer.main ingest --input scripts/.runtime/drafts-....json
python -m event_maintainer.main list-duplicates
python -m event_maintainer.main list-logs
python -m event_maintainer.main category-audit
```

## 环境与配置

- **Python**：`>=3.11`，项目根 `pip install -e ".[dev]"`
- **数据库路径**：`settings.json` 的 `database.path`（见 `settings.example.json`）或环境变量 `EVENT_DB_PATH`
- **维护窗口**：`settings.json` 的 `maintenance.past_hours` / `future_days`（默认 72 / 7），同步到 `.env` 的 `MAINTENANCE_PAST_HOURS` / `MAINTENANCE_FUTURE_DAYS`
- **Mem0**（可选）：`.env.example` 中 `MEM0_*`；默认 `MEM0_USER_ID=openclaw`

## 定时与无人值守

由 **OpenClaw 自身的调度/自动化** 触发维护任务（cron、OpenClaw Automation 等），提示词正文使用 `scripts/prompts/update-database.txt`。

若曾用本仓库旧版注册过 Windows 计划任务 `MacroMaintainer-UpdateDatabase`，可手动卸载：

```powershell
Unregister-ScheduledTask -TaskName MacroMaintainer-UpdateDatabase -Confirm:$false -ErrorAction SilentlyContinue
```

## 会话交付（OpenClaw 输出给用户）

与 `event_rules.mdc` 一致：目标分类、已执行 CLI、变更摘要、末次 `category-audit`、异常 `list-logs` / `list-duplicates`。

## 与 Cursor IDE 的关系

在 Cursor 中编辑本仓库仍可使用 `.cursor/rules` 与技能；**运行时维护不再依赖** `agent`、`.cursor/cli.json` 或 `scripts/run-maintain-agent.ps1`（已移除）。
