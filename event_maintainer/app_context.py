from __future__ import annotations

from dataclasses import dataclass

from event_maintainer.config import AppSettings
from event_maintainer.db import SQLiteEventStore
from event_maintainer.dedup import DedupService
from event_maintainer.maintenance import MaintenanceService
from event_maintainer.memory import Mem0MemoryStore
from event_maintainer.tools import ToolRegistry


@dataclass(frozen=True)
class AppContext:
    settings: AppSettings
    store: SQLiteEventStore
    memory: Mem0MemoryStore
    dedup: DedupService
    maintenance: MaintenanceService
    tools: ToolRegistry


def build_app_context(settings: AppSettings | None = None) -> AppContext:
    resolved_settings = settings or AppSettings()
    store = SQLiteEventStore(resolved_settings.db_path)
    memory = Mem0MemoryStore(resolved_settings)
    dedup = DedupService(
        store,
        memory,
        resolved_settings.mem0_dup_threshold,
        semantic_text_confirm_ratio=resolved_settings.mem0_text_confirm_ratio,
    )
    maintenance = MaintenanceService(
        store, dedup, memory, resolved_settings.category_registry_path
    )
    tools = ToolRegistry(store, dedup, maintenance)
    return AppContext(
        settings=resolved_settings,
        store=store,
        memory=memory,
        dedup=dedup,
        maintenance=maintenance,
        tools=tools,
    )
