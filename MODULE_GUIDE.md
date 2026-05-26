# Module guide

## `event_maintainer`

CLI maintenance, SQLite store (3 tables), dedup, optional Mem0 (pip extra `[mem0]`, local Chroma — no Docker; semantic dedup + 30-day `expires_on` metadata).

| Submodule | Responsibility |
|-----------|----------------|
| `db/` | `SQLiteEventStore` — schema, CRUD, logs |
| `maintenance/` | `MaintenanceService` — ingest, `update-event` |
| `category/` | Registry parse (`event_category.mdc`), `category-audit`, write validation |
| `dedup/` | Duplicate detection |
| `recency/` | Maintenance window (default past 72h + future 7d), `recency-window` / `recency-audit` |
| `tools/` | `ToolRegistry` — CLI-facing helpers |
| `project_settings.py` | Load `settings.json` — DB path, Mem0 flags, maintenance window (`maintenance.past_hours` / `future_days`) |
| `apps/api/` | FastAPI read API for iOS (no writes) |

### Maintenance orchestration (external)

- **OpenClaw** runs maintenance sessions; see [docs/OPENCLAW_MAINTENANCE.md](docs/OPENCLAW_MAINTENANCE.md).
- Prompt SSOT: `scripts/prompts/update-database.txt`
- Rules/skills: `.cursor/rules/*.mdc`, `.cursor/skills/maintain-events/SKILL.md`
- Draft JSON at ingest: prefer `scripts/.runtime/drafts-<timestamp>.json`

### Category registry

- SSOT: `.cursor/rules/event_category.mdc`
- Env override: `EVENT_CATEGORY_REGISTRY`
- CLI: `category-audit`, `update-event`; ingest rejects unregistered labels
- Events store ordered multi-category in `categories_json` (`categories[0]` = primary); `category` column mirrors primary for index/filter compat
