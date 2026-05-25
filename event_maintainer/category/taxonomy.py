from __future__ import annotations

from collections.abc import Sequence

from event_maintainer.category.registry import CategoryRegistry


def _validate_one_label(value: str, registry: CategoryRegistry) -> str | None:
    if registry.is_registered_label(value):
        return None
    suggestion = registry.suggest_label(value)
    if suggestion:
        return (
            f"category '{value}' is an alias; use registered label '{suggestion}'"
        )
    registered = ", ".join(sorted(registry.labels))
    return f"category '{value}' is not registered; allowed labels: {registered}"


def validate_category_for_write(value: str, registry: CategoryRegistry) -> str | None:
    """Return error message if category must not be written; None if OK or empty."""
    if not value:
        return None
    return _validate_one_label(value, registry)


def validate_categories_for_write(
    categories: Sequence[str], registry: CategoryRegistry
) -> str | None:
    """Validate ordered multi-category list. Empty list is allowed."""
    if not categories:
        return None
    for label in categories:
        error = _validate_one_label(label, registry)
        if error:
            return error
    return None