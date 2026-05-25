from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.dependencies import get_context
from apps.api.main import app
from event_maintainer.app_context import build_app_context
from event_maintainer.config import AppSettings
from event_maintainer.schemas import EventDraft


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    db_path = tmp_path / "api.sqlite3"
    monkeypatch.setenv("EVENT_DB_PATH", str(db_path))
    get_context.cache_clear()

    context = build_app_context(AppSettings(db_path=db_path, mem0_enabled=False))
    draft = EventDraft(
        title="美联储维持利率不变",
        source="FOMC",
        event_time="2026-05-18T14:00:00Z",
        end_time="2026-05-18T15:00:00Z",
        raw_content="美联储宣布维持利率不变。",
        summary="美联储宣布维持利率不变。",
        country="US",
        category="央行",
        importance_score=0.95,
        impact_score=0.88,
        analysis="利率维持不变。",
        symbols=("US500", "DXY"),
    )
    context.maintenance.ingest_events([draft])

    from apps.api.dependencies import get_store

    app.dependency_overrides[get_store] = lambda: context.store
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_context.cache_clear()


def test_list_events_requires_params(client: TestClient) -> None:
    response = client.get("/events/")
    assert response.status_code == 422


def test_list_events_in_shanghai_window(client: TestClient) -> None:
    response = client.get(
        "/events/",
        params={
            "event_date": "2026-05-18",
            "timezone": "Asia/Shanghai",
            "page_size": 0,
            "offset": 0,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
    assert body["items"][0]["title"]
    assert body["query_window"]["timezone"] == "Asia/Shanghai"


def test_get_event_detail(client: TestClient) -> None:
    listed = client.get(
        "/events/",
        params={"event_date": "2026-05-18", "timezone": "Asia/Shanghai"},
    ).json()
    event_id = listed["items"][0]["id"]
    detail = client.get(f"/events/{event_id}").json()
    assert detail["analysis"]
    assert detail["key_metrics"] == []
    assert "US500" in detail["related_assets"]


def test_search_events(client: TestClient) -> None:
    response = client.get("/search/", params={"q": "美联储", "limit": 10})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 1
