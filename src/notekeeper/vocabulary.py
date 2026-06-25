"""Controlled-vocabulary checks against TAGS.md, to catch sprawl early.

Without this, 'claude', 'claude-config', and 'claude_workflow' quietly
become three different tags meaning the same thing. validate() flags any
project/category/tag not already listed in TAGS.md, so adding a new one
is a deliberate choice rather than an accidental typo.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from notekeeper.notes import Note


@dataclass(frozen=True)
class Vocabulary:
    """The set of known projects, categories, and tags from TAGS.md."""

    projects: set[str]
    categories: set[str]
    tags: set[str]


def _parse_section(lines: list[str], heading: str) -> set[str]:
    """Extract bullet items under a given '## heading' in TAGS.md."""
    items: set[str] = set()
    in_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower() == f"## {heading}".lower():
            in_section = True
            continue
        if stripped.startswith("## "):
            in_section = False
            continue
        if in_section and stripped.startswith("-"):
            items.add(stripped.lstrip("- ").strip().lower())
    return items


def load_vocabulary(root_dir: Path) -> Vocabulary:
    """Read TAGS.md and return the controlled vocabulary, empty sets if missing."""
    tags_file = root_dir / "TAGS.md"
    if not tags_file.exists():
        return Vocabulary(projects=set(), categories=set(), tags=set())

    lines = tags_file.read_text(encoding="utf-8").splitlines()
    return Vocabulary(
        projects=_parse_section(lines, "projects"),
        categories=_parse_section(lines, "categories"),
        tags=_parse_section(lines, "tags"),
    )


def validate(notes: list[Note], vocabulary: Vocabulary) -> list[str]:
    """Return a list of human-readable warnings for any note using an unlisted value."""
    warnings: list[str] = []

    for note in notes:
        if not note.project:
            warnings.append(f"{note.path.name}: missing 'project'")
        elif vocabulary.projects and note.project.lower() not in vocabulary.projects:
            warnings.append(f"{note.path.name}: project '{note.project}' not in TAGS.md")

        if not note.category:
            warnings.append(f"{note.path.name}: missing 'category'")
        elif vocabulary.categories and note.category.lower() not in vocabulary.categories:
            warnings.append(f"{note.path.name}: category '{note.category}' not in TAGS.md")

        if vocabulary.tags:
            unknown_tags = [tag for tag in note.tags if tag not in vocabulary.tags]
            for tag in unknown_tags:
                warnings.append(f"{note.path.name}: tag '{tag}' not in TAGS.md")

    return warnings
