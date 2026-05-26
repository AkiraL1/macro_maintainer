# macro_maintainer

Macro event database: **3 SQLite tables**, **Python CLI** for writes, **FastAPI** for iOS read APIs. Maintenance reasoning and scheduling are done in **OpenClaw**; Python runs `ingest`, dedup, and `search-web`.

See [docs/OPENCLAW_MAINTENANCE.md](docs/OPENCLAW_MAINTENANCE.md) for orchestration SSOT (prompts, rules, skills).

## Install

```powershell
cd macro_maintainer_openclaw
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Copy [`settings.example.json`](settings.example.json) to `settings.json` to set DB path and maintenance window (optional; env vars in `.env` also work).

## Maintain (OpenClaw + Python)

Configure OpenClaw with this repo as workspace and load:

- `scripts/prompts/update-database.txt`
- `.cursor/skills/maintain-events/SKILL.md`
- `.cursor/rules/*.mdc`

Example CLI (OpenClaw invokes these; humans may run the same):

```powershell
python -m event_maintainer.main search-web --query "Fed rate decision 2026"
python -m event_maintainer.main init-db
python -m event_maintainer.main ingest --input examples/events.json
python -m event_maintainer.main db-status
```

## API (iOS)

```powershell
uvicorn apps.api.main:app --reload
# http://127.0.0.1:8000/docs
```

## Test

```powershell
pytest
```

See [MODULE_GUIDE.md](MODULE_GUIDE.md) and [docs/FRONTEND_DATA_ACCESS.md](docs/FRONTEND_DATA_ACCESS.md).
