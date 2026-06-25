"""Note loading, frontmatter parsing, and filtering for notekeeper notes.

Frontmatter is parsed with a minimal hand-rolled parser rather than
PyYAML, since the schema is small and fixed (see README.md) and avoiding
the dependency keeps this installable with zero external packages.

Performance note: a full directory scan on every search is effectively
instant for a personal notes collection (hundreds to low thousands of notes) and
simpler than maintaining an index. If the notes collection grows past that scale,
load these same frontmatter fields into a SQLite table instead of
re-scanning the filesystem on every call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path


@dataclass(frozen=True)
class Note:
    """A single parsed note."""

    path: Path
    project: str | None
    tags: list[str]
    category: str | None
    status: str | None
    date: str | None
    body: str


def _parse_list_value(raw: str) -> list[str]:
    """Parse a frontmatter list value like '[a, b, c]' into ['a', 'b', 'c'].

    Falls back to a single-item list if the value isn't bracketed, so a
    malformed entry doesn't crash the whole search.
    """
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1]
        return [item.strip() for item in inner.split(",") if item.strip()]
    return [raw] if raw else []


def parse_frontmatter(text: str) -> tuple[dict[str, str | list[str]], str]:
    """Split a note into its frontmatter dict and remaining body text.

    Expects the file to start with a '---' delimited block of flat
    'key: value' lines. Returns an empty dict (and the original text as
    body) if no frontmatter block is found, rather than raising — a note
    missing frontmatter should still be readable, just unsearchable by
    structured field.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text

    frontmatter: dict[str, str | list[str]] = {}
    end_index: int | None = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        frontmatter[key] = _parse_list_value(value) if value.startswith("[") else value

    if end_index is None:
        return {}, text

    body = "\n".join(lines[end_index + 1 :]).strip()
    return frontmatter, body


def load_note(path: Path) -> Note:
    """Read and parse a single note file from disk."""
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)

    tags_value = frontmatter.get("tags", [])
    tags = tags_value if isinstance(tags_value, list) else [tags_value]

    def _scalar(key: str) -> str | None:
        value = frontmatter.get(key)
        return value if isinstance(value, str) and value else None

    return Note(
        path=path,
        project=_scalar("project"),
        tags=[tag.lower() for tag in tags if tag],
        category=_scalar("category"),
        status=_scalar("status"),
        date=_scalar("date"),
        body=body,
    )


def iter_notes(root_dir: Path) -> list[Note]:
    """Load every markdown note found under root_dir/notes."""
    notes_dir = root_dir / "notes"
    if not notes_dir.exists():
        return []
    return [load_note(path) for path in sorted(notes_dir.glob("*.md"))]


def _fuzzy_contains(body_words: set[str], query_word: str, cutoff: float = 0.78) -> bool:
    """Check whether query_word appears in body_words, exactly or as a near-miss.

    Near-miss tolerance (cutoff) catches typos and minor variations without
    pulling in a fuzzy-matching dependency — difflib's ratio-based comparison
    is sufficient at the word level for a personal notes collection's note volume.
    """
    if query_word in body_words:
        return True
    return any(
        SequenceMatcher(None, query_word, word).ratio() >= cutoff for word in body_words
    )


def fuzzy_text_match(body: str, query: str, cutoff: float = 0.78) -> bool:
    """Return True if every word in query has an exact or near-miss match in body.

    Word-level fuzzy matching rather than whole-string similarity: it tolerates
    typos and near-synonyms per word while still requiring all query terms be
    present somewhere in the note, which keeps results relevant rather than
    just "vaguely similar."
    """
    query_words = re.findall(r"\w+", query.lower())
    if not query_words:
        return True
    body_words = set(re.findall(r"\w+", body.lower()))
    return all(_fuzzy_contains(body_words, word, cutoff) for word in query_words)


def text_match(body: str, query: str, fuzzy: bool) -> bool:
    """Check a note's body against a text query, exact substring or fuzzy."""
    if query.lower() in body.lower():
        return True
    return fuzzy_text_match(body, query) if fuzzy else False



def extract_links(body: str) -> list[str]:
    """Find [[note-stem]] style references in a note's body.

    Convention: [[some-note-filename-stem]] (no .md extension, no path) —
    deliberately plain text, not a special format, so the file stays
    readable and meaningful with or without tooling.
    """
    return re.findall(r"\[\[([^\]]+)\]\]", body)


def build_backlink_index(notes: list[Note]) -> dict[str, list[str]]:
    """Map each note stem to the list of distinct note stems that link to it."""
    index: dict[str, list[str]] = {}
    for note in notes:
        targets = set(extract_links(note.body))
        for target in targets:
            index.setdefault(target, []).append(note.path.stem)
    return index



def matches(
    note: Note,
    project: str | None = None,
    tag: str | None = None,
    category: str | None = None,
    status: str | None = None,
    text: str | None = None,
    fuzzy: bool = False,
) -> bool:
    """Check whether a note satisfies all given filters (AND logic).

    When fuzzy=True, project/category/tag use near-miss string comparison
    (typo tolerance) and text uses word-level fuzzy matching.
    """

    def _fuzzy_equal(value: str, target: str, cutoff: float = 0.82) -> bool:
        return SequenceMatcher(None, value.lower(), target.lower()).ratio() >= cutoff

    if project:
        if not note.project:
            return False
        if note.project != project and not (fuzzy and _fuzzy_equal(note.project, project)):
            return False
    if tag:
        tag_lower = tag.lower()
        if tag_lower not in note.tags and not (
            fuzzy and any(_fuzzy_equal(existing, tag_lower) for existing in note.tags)
        ):
            return False
    if category:
        if not note.category:
            return False
        if note.category != category and not (fuzzy and _fuzzy_equal(note.category, category)):
            return False
    if status and note.status != status:
        return False
    if text and not text_match(note.body, text, fuzzy):
        return False
    return True


def slugify(title: str) -> str:
    """Turn a note title into a filesystem-safe slug for the filename."""
    keep = [char.lower() if char.isalnum() else "-" for char in title.strip()]
    slug = "".join(keep)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def new_note_path(root_dir: Path, title: str, on: date | None = None) -> Path:
    """Compute the file path for a new note, following the YYYY-MM-DD-slug convention."""
    note_date = on or date.today()
    return root_dir / "notes" / f"{note_date.isoformat()}-{slugify(title)}.md"


def render_note(
    title: str,
    project: str | None,
    tags: list[str],
    category: str | None,
    status: str,
    on: date | None = None,
) -> str:
    """Render a new note's full text, frontmatter plus a starter body."""
    note_date = on or date.today()
    tags_str = "[" + ", ".join(tags) + "]" if tags else "[]"
    return (
        "---\n"
        f"project: {project or ''}\n"
        f"tags: {tags_str}\n"
        f"category: {category or ''}\n"
        f"status: {status}\n"
        f"date: {note_date.isoformat()}\n"
        "---\n\n"
        f"# {title}\n\n"
    )
