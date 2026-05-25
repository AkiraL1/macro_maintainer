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
| `gui/` | CustomTkinter desktop panel — edit `settings.json`, workflow display, subprocess triggers |
| `project_settings.py` | Load/save `settings.json`, `.env` sync, unattended schedule defaults (`unattended.enabled` false) |
| `unattended_schedule.py` | Sync Task Scheduler with `settings.json`; GUI startup + save |
| `apps/api/` | FastAPI read API for iOS (no writes) |

### Category registry

- SSOT: `.cursor/rules/event_category.mdc`
- Env override: `EVENT_CATEGORY_REGISTRY`
- CLI: `category-audit`, `update-event`; ingest rejects unregistered labels
- Events store ordered multi-category in `categories_json` (`categories[0]` = primary); `category` column mirrors primary for index/filter compat
