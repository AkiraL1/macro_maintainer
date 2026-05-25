from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _load_settings() -> dict[str, Any]:
    settings_path = Path(os.getenv("EVENT_MAINTAINER_SETTINGS", "./settings.json"))
    if not settings_path.exists():
        return {}
    return json.loads(settings_path.read_text(encoding="utf-8"))


def _setting(settings: dict[str, Any], dotted_path: str, default: Any) -> Any:
    current: Any = settings
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return default
        current = current[part]
    return current


SETTINGS = _load_settings()


@dataclass(frozen=True)
class AppSettings:
    db_path: Path = Path(
        os.getenv(
            "EVENT_DB_PATH",
            _setting(SETTINGS, "database.path", "./macro_maintainer.sqlite3"),
        )
    )
    mem0_enabled: bool = _env_bool(
        "MEM0_ENABLED", bool(_setting(SETTINGS, "mem0.enabled", False))
    )
    mem0_config_path: Path | None = (
        Path(os.environ["MEM0_CONFIG_PATH"]) if os.getenv("MEM0_CONFIG_PATH") else None
    )
    mem0_dup_threshold: float = float(
        os.getenv(
            "MEM0_DUP_THRESHOLD", _setting(SETTINGS, "mem0.dup_threshold", "0.85")
        )
    )
    mem0_text_confirm_ratio: float = float(
        os.getenv(
            "MEM0_TEXT_CONFIRM_RATIO",
            _setting(SETTINGS, "mem0.text_confirm_ratio", "0.75"),
        )
    )
    mem0_user_id: str = os.getenv(
        "MEM0_USER_ID", _setting(SETTINGS, "mem0.user_id", "cursor-agent")
    )
    mem0_run_id: str = os.getenv(
        "MEM0_RUN_ID", _setting(SETTINGS, "mem0.run_id", "event-maintenance")
    )
    mem0_collection_name: str = os.getenv(
        "MEM0_COLLECTION_NAME",
        _setting(SETTINGS, "mem0.collection_name", "global_events"),
    )
    mem0_history_db_path: Path = Path(
        os.getenv(
            "MEM0_HISTORY_DB_PATH",
            _setting(SETTINGS, "mem0.history_db_path", "./mem0_history.db"),
        )
    )
    mem0_llm_provider: str = os.getenv(
        "MEM0_LLM_PROVIDER", _setting(SETTINGS, "mem0.llm.provider", "openai")
    )
    mem0_llm_model: str = os.getenv(
        "MEM0_LLM_MODEL", _setting(SETTINGS, "mem0.llm.model", "deepseek-chat")
    )
    mem0_llm_base_url: str = os.getenv(
        "MEM0_LLM_BASE_URL",
        _setting(SETTINGS, "mem0.llm.base_url", "https://api.deepseek.com"),
    )
    mem0_llm_api_key_env: str = os.getenv(
        "MEM0_LLM_API_KEY_ENV",
        _setting(SETTINGS, "mem0.llm.api_key_env", "DEEPSEEK_API_KEY"),
    )
    mem0_llm_thinking: bool = _env_bool(
        "MEM0_LLM_THINKING", bool(_setting(SETTINGS, "mem0.llm.thinking", False))
    )
    mem0_embedder_provider: str = os.getenv(
        "MEM0_EMBEDDER_PROVIDER", _setting(SETTINGS, "mem0.embedder.provider", "openai")
    )
    mem0_embedder_model: str = os.getenv(
        "MEM0_EMBEDDER_MODEL",
        _setting(SETTINGS, "mem0.embedder.model", "text-embedding-v4"),
    )
    mem0_embedder_base_url: str = os.getenv(
        "MEM0_EMBEDDER_BASE_URL",
        _setting(
            SETTINGS,
            "mem0.embedder.base_url",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
    )
    mem0_embedder_api_key_env: str = os.getenv(
        "MEM0_EMBEDDER_API_KEY_ENV",
        _setting(SETTINGS, "mem0.embedder.api_key_env", "DASHSCOPE_API_KEY"),
    )
    mem0_vector_store_provider: str = os.getenv(
        "MEM0_VECTOR_STORE_PROVIDER",
        _setting(SETTINGS, "mem0.vector_store.provider", "chroma"),
    )
    mem0_vector_store_path: Path = Path(
        os.getenv(
            "MEM0_VECTOR_STORE_PATH",
            _setting(SETTINGS, "mem0.vector_store.path", "./mem0_chroma"),
        )
    )
    mem0_ttl_days: int = int(
        os.getenv("MEM0_TTL_DAYS", _setting(SETTINGS, "mem0.ttl_days", "30"))
    )
    mem0_prune_on_start: bool = _env_bool(
        "MEM0_PRUNE_ON_START", bool(_setting(SETTINGS, "mem0.prune_on_start", True))
    )
    mem0_infer_on_add: bool = _env_bool(
        "MEM0_INFER_ON_ADD", bool(_setting(SETTINGS, "mem0.infer_on_add", False))
    )
    category_registry_path: Path = Path(
        os.getenv(
            "EVENT_CATEGORY_REGISTRY",
            _setting(
                SETTINGS,
                "category.registry_path",
                str(
                    Path(__file__).resolve().parents[1]
                    / ".cursor"
                    / "rules"
                    / "event_category.mdc"
                ),
            ),
        )
    )
