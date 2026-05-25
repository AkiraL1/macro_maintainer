from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from event_maintainer.schemas import (
    DedupDecision,
    EventDraft,
    KeyMetricDraft,
    StoredEvent,
)
from event_maintainer.schemas.categories import normalize_categories, primary_category
from event_maintainer.schemas.events import utc_now_iso

_DDL = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    event_time TEXT NOT NULL,
    end_time TEXT,
    raw_content TEXT NOT NULL,
    summary TEXT NOT NULL,
    content TEXT NOT NULL,
    country TEXT NOT NULL,
    category TEXT NOT NULL,
    categories_json TEXT NOT NULL DEFAULT '[]',
    importance_score REAL NOT NULL,
    impact_score REAL NOT NULL,
    analysis TEXT NOT NULL DEFAULT '',
    symbols_json TEXT NOT NULL DEFAULT '[]',
    key_metrics_json TEXT NOT NULL DEFAULT '[]',
    related_event_ids_json TEXT NOT NULL DEFAULT '[]',
    extras_json TEXT NOT NULL DEFAULT '{}',
    dedup_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_event_time ON events(event_time);
CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);

CREATE TABLE IF NOT EXISTS event_duplicates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedup_hash TEXT NOT NULL,
    duplicate_event_id TEXT,
    reason TEXT NOT NULL,
    score REAL NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_event_duplicates_hash ON event_duplicates(dedup_hash);

CREATE TABLE IF NOT EXISTS maintenance_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL,
    event_id TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_maintenance_logs_created ON maintenance_logs(created_at);
"""


class SQLiteEventStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(_DDL)
            self._migrate_categories_json(connection)

    @staticmethod
    def _migrate_categories_json(connection: sqlite3.Connection) -> None:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(events)").fetchall()
        }
        if "categories_json" not in columns:
            connection.execute(
                "ALTER TABLE events ADD COLUMN categories_json TEXT NOT NULL DEFAULT '[]'"
            )
        rows = connection.execute(
            "SELECT id, category, categories_json FROM events"
        ).fetchall()
        for row in rows:
            raw_json = row["categories_json"] or "[]"
            try:
                parsed = json.loads(raw_json)
            except json.JSONDecodeError:
                parsed = []
            if isinstance(parsed, list) and parsed:
                labels = normalize_categories(categories=tuple(str(x) for x in parsed))
            else:
                labels = normalize_categories(legacy_category=row["category"] or "")
            primary = primary_category(labels)
            payload = json.dumps(list(labels), ensure_ascii=False)
            if payload != raw_json or (row["category"] or "") != primary:
                connection.execute(
                    """
                    UPDATE events
                    SET categories_json = ?, category = ?
                    WHERE id = ?
                    """,
                    (payload, primary, row["id"]),
                )

    def database_status(self) -> dict[str, Any]:
        with self._connect() as connection:
            tables = self._list_tables(connection)
            counts = {
                table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in tables
            }
        return {
            "db_path": str(self.db_path),
            "exists": self.db_path.exists(),
            "tables": tables,
            "row_counts": counts,
        }

    def find_by_dedup_hash(self, dedup_hash: str) -> StoredEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE dedup_hash = ?",
                (dedup_hash,),
            ).fetchone()
        return self._row_to_event(row) if row else None

    def find_by_fingerprint(self, fingerprint: str) -> StoredEvent | None:
        return self.find_by_dedup_hash(fingerprint)

    def get_event(self, event_id: str) -> StoredEvent | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM events WHERE id = ?",
                (event_id,),
            ).fetchone()
        return self._row_to_event(row) if row else None

    def upsert_event(self, draft: EventDraft) -> StoredEvent:
        dedup_hash = draft.dedup_hash()
        existing = self.find_by_dedup_hash(dedup_hash)
        if existing:
            return existing

        now = utc_now_iso()
        event_id = str(uuid.uuid4())
        content = draft.content or draft.raw_content
        event_time = _dt_to_compare_iso(parse_event_time(draft.event_time))
        end_time = (
            _dt_to_compare_iso(parse_event_time(draft.end_time))
            if draft.end_time
            else None
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO events (
                    id, title, source, event_time, end_time, raw_content, summary, content,
                    country, category, categories_json, importance_score, impact_score,
                    analysis, symbols_json, key_metrics_json, related_event_ids_json,
                    extras_json, dedup_hash, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    draft.title,
                    draft.source,
                    event_time,
                    end_time,
                    draft.raw_content,
                    draft.summary,
                    content,
                    draft.country,
                    draft.category,
                    json.dumps(list(draft.categories), ensure_ascii=False),
                    draft.importance_score,
                    draft.impact_score,
                    draft.analysis,
                    json.dumps(list(draft.symbols), ensure_ascii=False),
                    json.dumps(
                        [m.to_dict() for m in draft.key_metrics], ensure_ascii=False
                    ),
                    json.dumps(list(draft.related_event_ids), ensure_ascii=False),
                    json.dumps(draft.extras, ensure_ascii=False),
                    dedup_hash,
                    now,
                    now,
                ),
            )
        return StoredEvent(event_id, draft, dedup_hash, now, now)

    def record_duplicate(self, dedup_hash: str, decision: DedupDecision) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO event_duplicates (
                    dedup_hash, duplicate_event_id, reason, score, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    dedup_hash,
                    decision.duplicate_event_id,
                    decision.reason,
                    decision.score,
                    utc_now_iso(),
                ),
            )
            return int(cursor.lastrowid)

    def record_log(
        self,
        action: str,
        status: str,
        detail: str,
        event_id: str | None = None,
    ) -> int:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO maintenance_logs (action, status, detail, event_id, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (action, status, detail, event_id, utc_now_iso()),
            )
            return int(cursor.lastrowid)

    def list_events(self) -> list[StoredEvent]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events ORDER BY event_time DESC"
            ).fetchall()
        return [self._row_to_event(row) for row in rows]

    def list_events_in_time_window(
        self,
        start_utc: datetime,
        end_utc: datetime,
        *,
        source: str | None = None,
        country: str | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int | None = None,
    ) -> tuple[list[StoredEvent], int]:
        start_iso = _dt_to_compare_iso(start_utc)
        end_iso = _dt_to_compare_iso(end_utc)
        clauses = ["event_time >= ?", "event_time < ?"]
        params: list[Any] = [start_iso, end_iso]
        if source:
            clauses.append("source = ?")
            params.append(source)
        if country:
            clauses.append("country = ?")
            params.append(country)
        if category:
            clauses.append(
                """
                (
                    category = ?
                    OR EXISTS (
                        SELECT 1 FROM json_each(events.categories_json) AS cat
                        WHERE cat.value = ?
                    )
                )
                """
            )
            params.extend([category, category])
        where = " AND ".join(clauses)
        with self._connect() as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM events WHERE {where}",
                params,
            ).fetchone()[0]
            query = f"SELECT * FROM events WHERE {where} ORDER BY event_time DESC"
            if limit is not None:
                query += " LIMIT ? OFFSET ?"
                rows = connection.execute(query, [*params, limit, offset]).fetchall()
            else:
                if offset:
                    query += " OFFSET ?"
                    rows = connection.execute(query, [*params, offset]).fetchall()
                else:
                    rows = connection.execute(query, params).fetchall()
        return [self._row_to_event(row) for row in rows], int(total)

    def search_events_text(
        self, query: str, *, limit: int = 20
    ) -> tuple[list[StoredEvent], int]:
        pattern = f"%{query.lower()}%"
        with self._connect() as connection:
            total = connection.execute(
                """
                SELECT COUNT(*) FROM events
                WHERE lower(title) LIKE ? OR lower(summary) LIKE ?
                   OR lower(content) LIKE ? OR lower(raw_content) LIKE ?
                """,
                (pattern, pattern, pattern, pattern),
            ).fetchone()[0]
            rows = connection.execute(
                """
                SELECT * FROM events
                WHERE lower(title) LIKE ? OR lower(summary) LIKE ?
                   OR lower(content) LIKE ? OR lower(raw_content) LIKE ?
                ORDER BY event_time DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        return [self._row_to_event(row) for row in rows], int(total)

    def list_duplicate_records(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM event_duplicates ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def list_maintenance_logs(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM maintenance_logs ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def category_counts(self) -> dict[str, int]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT cat.value AS label, COUNT(DISTINCT events.id) AS cnt
                FROM events, json_each(events.categories_json) AS cat
                GROUP BY cat.value
                """
            ).fetchall()
        return {str(row["label"]): int(row["cnt"]) for row in rows}

    def update_event_fields(
        self,
        event_id: str,
        *,
        categories: tuple[str, ...] | None = None,
        category: str | None = None,
        summary: str | None = None,
        country: str | None = None,
    ) -> StoredEvent | None:
        existing = self.get_event(event_id)
        if not existing:
            return None
        draft = existing.draft
        if categories is not None:
            next_categories = categories
        elif category is not None:
            next_categories = normalize_categories(legacy_category=category)
        else:
            next_categories = draft.categories
        updated = EventDraft(
            title=draft.title,
            source=draft.source,
            event_time=draft.event_time,
            raw_content=draft.raw_content,
            summary=summary if summary is not None else draft.summary,
            content=draft.content,
            country=country if country is not None else draft.country,
            categories=next_categories,
            importance_score=draft.importance_score,
            impact_score=draft.impact_score,
            symbols=draft.symbols,
            analysis=draft.analysis,
            end_time=draft.end_time,
            key_metrics=draft.key_metrics,
            related_event_ids=draft.related_event_ids,
            extras=draft.extras,
        )
        now = utc_now_iso()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE events
                SET summary = ?, country = ?, category = ?, categories_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    updated.summary,
                    updated.country,
                    updated.category,
                    json.dumps(list(updated.categories), ensure_ascii=False),
                    now,
                    event_id,
                ),
            )
        return StoredEvent(
            id=existing.id,
            draft=updated,
            dedup_hash=existing.dedup_hash,
            created_at=existing.created_at,
            updated_at=now,
        )

    def event_to_dict(self, event: StoredEvent) -> dict[str, Any]:
        row = self.get_event(event.id)
        if not row:
            return {}
        return self._stored_to_api_dict(row)

    def _stored_to_api_dict(self, event: StoredEvent) -> dict[str, Any]:
        draft = event.draft
        event_time = parse_event_time(draft.event_time)
        return {
            "id": event.id,
            "title": draft.title,
            "source": draft.source,
            "event_time": event_time,
            "event_date": event_time.date(),
            "end_time": parse_event_time(draft.end_time) if draft.end_time else None,
            "summary": draft.summary,
            "content": draft.content or draft.raw_content,
            "raw_content": draft.raw_content,
            "country": draft.country,
            "category": draft.category,
            "categories": list(draft.categories),
            "importance_score": draft.importance_score,
            "impact_score": draft.impact_score,
            "analysis": draft.analysis,
            "symbols": list(draft.symbols),
            "key_metrics": [m.to_dict() for m in draft.key_metrics],
            "related_event_ids": list(draft.related_event_ids),
            "extras": draft.extras,
            "dedup_hash": event.dedup_hash,
            "created_at": event.created_at,
            "updated_at": event.updated_at,
        }

    @staticmethod
    def _list_tables(connection: sqlite3.Connection) -> list[str]:
        rows = connection.execute(
            """
            SELECT name FROM sqlite_master
            WHERE type = 'table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()
        return [str(row["name"]) for row in rows]

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> StoredEvent:
        symbols = json.loads(row["symbols_json"] or "[]")
        metrics_raw = json.loads(row["key_metrics_json"] or "[]")
        related = json.loads(row["related_event_ids_json"] or "[]")
        extras = json.loads(row["extras_json"] or "{}")
        categories_raw = json.loads(row["categories_json"] or "[]")
        if not isinstance(categories_raw, list):
            categories_raw = []
        categories = normalize_categories(
            categories=tuple(str(item) for item in categories_raw),
            legacy_category=row["category"] or "",
        )
        key_metrics = tuple(
            KeyMetricDraft(
                id=item.get("id"),
                name=str(item.get("name", "")),
                value=str(item.get("value", "")),
                previous_value=item.get("previous_value"),
                change=item.get("change"),
                unit=item.get("unit"),
            )
            for item in metrics_raw
            if isinstance(item, dict)
        )
        draft = EventDraft(
            title=row["title"],
            source=row["source"],
            event_time=row["event_time"],
            raw_content=row["raw_content"],
            summary=row["summary"],
            content=row["content"],
            country=row["country"],
            categories=categories,
            importance_score=row["importance_score"],
            impact_score=row["impact_score"],
            symbols=tuple(str(s) for s in symbols),
            analysis=row["analysis"] or "",
            end_time=row["end_time"],
            key_metrics=key_metrics,
            related_event_ids=tuple(str(r) for r in related),
            extras=extras if isinstance(extras, dict) else {},
        )
        return StoredEvent(
            id=row["id"],
            draft=draft,
            dedup_hash=row["dedup_hash"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )


def parse_event_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _dt_to_compare_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    normalized = dt.astimezone(timezone.utc)
    return normalized.strftime("%Y-%m-%dT%H:%M:%S") + "Z"
