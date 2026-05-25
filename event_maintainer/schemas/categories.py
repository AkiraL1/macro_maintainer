from __future__ import annotations


def normalize_categories(
    *,
    categories: tuple[str, ...] | list[str] | None = None,
    legacy_category: str = "",
) -> tuple[str, ...]:
    """Ordered labels: index 0 = strongest association. Dedupe keeps first occurrence."""
    ordered: list[str] = []
    seen: set[str] = set()
    if categories:
        for raw in categories:
            label = str(raw).strip()
            if not label or label in seen:
                continue
            seen.add(label)
            ordered.append(label)
    elif legacy_category:
        label = legacy_category.strip()
        if label:
            ordered.append(label)
    return tuple(ordered)


def primary_category(categories: tuple[str, ...]) -> str:
    return categories[0] if categories else ""
