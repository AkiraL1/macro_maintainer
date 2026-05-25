from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any

from event_maintainer.config import AppSettings
from event_maintainer.schemas import EventDraft, StoredEvent


@dataclass(frozen=True)
class MemorySearchResult:
    memory: str
    score: float
    event_id: str | None = None


def l2_distance_to_similarity(distance: float) -> float:
    """Map Chroma L2 distance (lower = closer) to similarity in (0, 1]."""
    if distance <= 0:
        return 1.0
    return 1.0 / (1.0 + distance)


def expires_on_date(ttl_days: int, *, now: datetime | None = None) -> str:
    """ISO date (YYYY-MM-DD) when a memory should be treated as expired."""
    anchor = now or datetime.now(timezone.utc)
    return (anchor + timedelta(days=ttl_days)).strftime("%Y-%m-%d")


def is_metadata_expired(metadata: dict[str, Any], *, today: date | None = None) -> bool:
    raw = metadata.get("expires_on")
    if not raw:
        return False
    try:
        expiry = date.fromisoformat(str(raw))
    except ValueError:
        return False
    current = today or datetime.now(timezone.utc).date()
    return current > expiry


class Mem0MemoryStore:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings
        self._memory: Any | None = None
        self._local_memories: list[tuple[str, str | None, str | None]] = []
        if settings.mem0_enabled:
            self._memory = self._build_mem0(settings)
            if settings.mem0_prune_on_start:
                self.prune_expired()

    def search_similar_events(self, draft: EventDraft, limit: int = 5) -> list[MemorySearchResult]:
        query = draft.memory_text()
        if not self._memory:
            return self._local_search(query, limit)
        # mem0.search() maps Chroma L2 distance into a 0–1 "score" incorrectly (often 1.0).
        return self._search_chroma_similarity(query, limit)

    def _search_chroma_similarity(
        self, query: str, limit: int
    ) -> list[MemorySearchResult]:
        """Use raw Chroma distances and convert to similarity in [0, 1]."""
        embeddings = self._memory.embedding_model.embed(query, "search")
        filters = {"user_id": self.settings.mem0_user_id}
        rows = self._memory.vector_store.search(
            query=query,
            vectors=embeddings,
            top_k=limit,
            filters=filters,
        )
        results: list[MemorySearchResult] = []
        for row in rows:
            distance = float(row.score) if row.score is not None else 999.0
            similarity = l2_distance_to_similarity(distance)
            payload = row.payload or {}
            if is_metadata_expired(payload):
                continue
            results.append(
                MemorySearchResult(
                    memory=str(payload.get("data") or ""),
                    score=similarity,
                    event_id=payload.get("event_id"),
                )
            )
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]

    def add_event_memory(self, event: StoredEvent) -> None:
        text = event.draft.memory_text()
        metadata = self._metadata_with_ttl(
            {"event_id": event.id, "dedup_hash": event.dedup_hash, "kind": "event"}
        )
        if not self._memory:
            self._local_memories.append((text, event.id, metadata.get("expires_on")))
            return

        self._memory.add(
            messages=text,
            user_id=self.settings.mem0_user_id,
            run_id=self.settings.mem0_run_id,
            metadata=metadata,
            infer=self.settings.mem0_infer_on_add,
        )

    def add_run_memory(self, summary: str) -> None:
        metadata = self._metadata_with_ttl({"kind": "maintenance_run"})
        if not self._memory:
            self._local_memories.append((summary, None, metadata.get("expires_on")))
            return
        self._memory.add(
            messages=summary,
            user_id=self.settings.mem0_user_id,
            run_id=self.settings.mem0_run_id,
            metadata=metadata,
            infer=self.settings.mem0_infer_on_add,
        )

    def prune_expired(self) -> int:
        """Delete mem0 rows whose metadata expires_on is before today."""
        if not self._memory:
            return self._prune_local_expired()

        removed = 0
        try:
            payload = self._memory.get_all(
                filters={"user_id": self.settings.mem0_user_id},
                top_k=500,
            )
        except (TypeError, ValueError):
            return 0

        items = payload.get("results", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return 0

        for item in items:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata") or {}
            if not is_metadata_expired(metadata):
                continue
            memory_id = item.get("id")
            if not memory_id:
                continue
            self._memory.delete(memory_id)
            removed += 1
        return removed

    def _metadata_with_ttl(self, base: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        if self.settings.mem0_ttl_days > 0:
            merged["expires_on"] = expires_on_date(self.settings.mem0_ttl_days)
        return merged

    def _build_mem0(self, settings: AppSettings) -> Any:
        try:
            from mem0 import Memory
        except ImportError as exc:
            raise RuntimeError(
                "mem0 is enabled but the OSS mem0 package is not installed. "
                "Install with `pip install -e \".[mem0]\"`."
            ) from exc

        config = self._load_config(settings)
        return Memory.from_config(config)

    def _prune_local_expired(self) -> int:
        kept: list[tuple[str, str | None, str | None]] = []
        removed = 0
        for text, event_id, expires_on in self._local_memories:
            if expires_on and is_metadata_expired({"expires_on": expires_on}):
                removed += 1
                continue
            kept.append((text, event_id, expires_on))
        self._local_memories = kept
        return removed

    def _local_search(self, query: str, limit: int) -> list[MemorySearchResult]:
        results = [
            MemorySearchResult(
                memory=memory,
                score=SequenceMatcher(None, query, memory).ratio(),
                event_id=event_id,
            )
            for memory, event_id, expires_on in self._local_memories
            if not (expires_on and is_metadata_expired({"expires_on": expires_on}))
        ]
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]

    @staticmethod
    def _load_config(settings: AppSettings) -> dict[str, Any]:
        if settings.mem0_config_path:
            raw = json.loads(settings.mem0_config_path.read_text(encoding="utf-8"))
            return normalize_mem0_config(raw)
        return build_default_mem0_config(settings)

    @staticmethod
    def _normalize_results(raw_results: Any) -> list[MemorySearchResult]:
        if isinstance(raw_results, dict):
            items = raw_results.get("results", [])
        else:
            items = raw_results or []

        normalized: list[MemorySearchResult] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            metadata = item.get("metadata") or {}
            if is_metadata_expired(metadata):
                continue
            normalized.append(
                MemorySearchResult(
                    memory=str(item.get("memory") or item.get("text") or ""),
                    score=float(item.get("score") or item.get("similarity") or 0.0),
                    event_id=metadata.get("event_id"),
                )
            )
        return normalized


def _provider_config_for_mem0(config: dict[str, Any]) -> dict[str, Any]:
    """Map legacy ``base_url`` to mem0 2.x ``openai_base_url`` (OpenAI-compatible APIs)."""
    normalized = dict(config)
    legacy_base = normalized.pop("base_url", None)
    if legacy_base is not None and "openai_base_url" not in normalized:
        normalized["openai_base_url"] = legacy_base
    return normalized


def normalize_mem0_config(config: dict[str, Any]) -> dict[str, Any]:
    """Normalize top-level mem0 JSON config (file or programmatic)."""
    normalized = dict(config)
    for section in ("llm", "embedder"):
        block = normalized.get(section)
        if not isinstance(block, dict):
            continue
        inner = block.get("config")
        if isinstance(inner, dict):
            block = dict(block)
            block["config"] = _provider_config_for_mem0(inner)
            normalized[section] = block
    return normalized


def build_default_mem0_config(settings: AppSettings) -> dict[str, Any]:
    llm_config: dict[str, Any] = {
        "model": settings.mem0_llm_model,
        "temperature": 0.1,
        "openai_base_url": settings.mem0_llm_base_url,
    }
    embedder_api_key = os.getenv(settings.mem0_embedder_api_key_env)
    llm_api_key = os.getenv(settings.mem0_llm_api_key_env)
    if llm_api_key:
        llm_config["api_key"] = llm_api_key
    elif embedder_api_key:
        # mem0 always constructs an LLM client; reuse DashScope-compatible creds when
        # DEEPSEEK_API_KEY is unset and infer-on-add is off (dedup/search only).
        llm_config["api_key"] = embedder_api_key
        llm_config["openai_base_url"] = settings.mem0_embedder_base_url
        llm_config["model"] = os.getenv("MEM0_LLM_FALLBACK_MODEL", "qwen-turbo")
    if settings.mem0_llm_thinking:
        llm_config["extra_body"] = {"thinking": True}

    embedder_config: dict[str, Any] = {
        "model": settings.mem0_embedder_model,
        "openai_base_url": settings.mem0_embedder_base_url,
    }
    if embedder_api_key:
        embedder_config["api_key"] = embedder_api_key

    return {
        "version": "v1.1",
        "history_db_path": str(settings.mem0_history_db_path),
        "llm": {"provider": settings.mem0_llm_provider, "config": llm_config},
        "embedder": {"provider": settings.mem0_embedder_provider, "config": embedder_config},
        "vector_store": {
            "provider": settings.mem0_vector_store_provider,
            "config": {
                "collection_name": settings.mem0_collection_name,
                "path": str(settings.mem0_vector_store_path),
            },
        },
    }
