# macro_maintainer

Macro event database: **3 SQLite tables**, **Python CLI** for writes, **FastAPI** for iOS read APIs. Maintenance reasoning is done in **Cursor CLI** (`agent`); Python runs `ingest`, dedup, and `search-web`.

## Install

```powershell
cd macro_maintainer
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Desktop GUI (control panel)

```powershell
pip install -e ".[dev,gui]"
python -m event_maintainer.gui
# or: .\scripts\launch-gui.ps1
```

Edit and save [`settings.json`](settings.json) (copy from [`settings.example.json`](settings.example.json)); syncs key fields to `.env`. Unattended scheduled task is **off** by default (`unattended.enabled: false`). Also: maintenance workflow steps and CLI / script triggers.

## Maintain (Cursor CLI + Python)

```powershell
agent
# Skill: /maintain-events

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
