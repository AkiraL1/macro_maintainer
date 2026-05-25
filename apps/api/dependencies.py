from functools import lru_cache

from event_maintainer.app_context import AppContext, build_app_context
from event_maintainer.db import SQLiteEventStore


@lru_cache
def get_context() -> AppContext:
    return build_app_context()


def get_store() -> SQLiteEventStore:
    return get_context().store
