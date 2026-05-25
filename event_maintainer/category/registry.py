from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CategoryEntry:
    label: str
    aliases: frozenset[str]
    examples: str = ""


@dataclass(frozen=True)
class CategoryRegistry:
    path: Path
    entries: tuple[CategoryEntry, ...]

    @property
    def labels(self) -> frozenset[str]:
        return frozenset(entry.label for entry in self.entries)

    def alias_to_label(self) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for entry in self.entries:
            for alias in entry.aliases:
                mapping[alias] = entry.label
        return mapping

    def is_registered_label(self, value: str) -> bool:
        return value in self.labels

    def suggest_label(self, value: str) -> str | None:
        return self.alias_to_label().get(value)


def default_registry_path() -> Path:
    override = os.getenv("EVENT_CATEGORY_REGISTRY")
    if override:
        return Path(override)
    project_root = Path(__file__).resolve().parents[2]
    return project_root / ".cursor" / "rules" / "event_category.mdc"


def load_registry(path: Path | None = None) -> CategoryRegistry:
    registry_path = path or default_registry_path()
    content = registry_path.read_text(encoding="utf-8")
    entries = _parse_categories_from_frontmatter(content)
    return CategoryRegistry(path=registry_path, entries=tuple(entries))


def _parse_categories_from_frontmatter(content: str) -> list[CategoryEntry]:
    if not content.startswith("---"):
        raise ValueError("event_category.mdc must start with YAML frontmatter")
    end = content.find("\n---", 3)
    if end == -1:
        raise ValueError("event_category.mdc frontmatter is not closed")
    body = content[3:end]
    entries: list[CategoryEntry] = []
    current_label: str | None = None
    current_aliases: set[str] = set()
    current_examples = ""

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        label_match = re.match(r"^-\s*label:\s*(.+)$", line)
        if label_match:
            if current_label is not None:
                entries.append(
                    CategoryEntry(
                        label=current_label,
                        aliases=frozenset(current_aliases),
                        examples=current_examples,
                    )
                )
            current_label = label_match.group(1).strip().strip("'\"")
            current_aliases = set()
            current_examples = ""
            continue
        if current_label is None:
            continue
        alias_match = re.match(r"^aliases:\s*\[(.*)\]\s*$", line)
        if alias_match:
            inner = alias_match.group(1).strip()
            if inner:
                current_aliases = {
                    part.strip().strip("'\"") for part in inner.split(",") if part.strip()
                }
            continue
        examples_match = re.match(r"^examples:\s*(.+)$", line)
        if examples_match:
            current_examples = examples_match.group(1).strip().strip("'\"")
            continue

    if current_label is not None:
        entries.append(
            CategoryEntry(
                label=current_label,
                aliases=frozenset(current_aliases),
                examples=current_examples,
            )
        )
    if not entries:
        raise ValueError("no categories found in event_category.mdc frontmatter")
    return entries
