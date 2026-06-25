"""Tests for notekeeper.notes — frontmatter parsing, fuzzy matching, and backlinks."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from notekeeper.notes import (
    Note,
    _fuzzy_contains,
    _parse_list_value,
    build_backlink_index,
    extract_links,
    fuzzy_text_match,
    load_note,
    matches,
    new_note_path,
    parse_frontmatter,
    render_note,
    slugify,
    text_match,
)


# ---------------------------------------------------------------------------
# _parse_list_value
# ---------------------------------------------------------------------------


class TestParseListValue:
    def test_bracketed_multiple(self) -> None:
        assert _parse_list_value("[a, b, c]") == ["a", "b", "c"]

    def test_bracketed_single(self) -> None:
        assert _parse_list_value("[python]") == ["python"]

    def test_bracketed_empty(self) -> None:
        assert _parse_list_value("[]") == []

    def test_unbracketed_single(self) -> None:
        assert _parse_list_value("python") == ["python"]

    def test_empty_string(self) -> None:
        assert _parse_list_value("") == []

    def test_strips_whitespace_from_items(self) -> None:
        assert _parse_list_value("[ foo ,  bar ]") == ["foo", "bar"]

    def test_ignores_empty_items_inside_brackets(self) -> None:
        # e.g. trailing comma: "[a, b, ]"
        assert _parse_list_value("[a, b, ]") == ["a", "b"]


# ---------------------------------------------------------------------------
# parse_frontmatter
# ---------------------------------------------------------------------------


FULL_FRONTMATTER = """\
---
project: my-project
tags: [python, cli]
category: dev
status: active
date: 2026-01-15
---

# Title

Body text here.
"""

NO_FRONTMATTER = """\
# Title

No frontmatter in this file.
"""

UNCLOSED_FRONTMATTER = """\
---
project: orphan
tags: [a]
"""


class TestParseFrontmatter:
    def test_parses_scalar_fields(self) -> None:
        fm, _ = parse_frontmatter(FULL_FRONTMATTER)
        assert fm["project"] == "my-project"
        assert fm["category"] == "dev"
        assert fm["status"] == "active"
        assert fm["date"] == "2026-01-15"

    def test_parses_list_field(self) -> None:
        fm, _ = parse_frontmatter(FULL_FRONTMATTER)
        assert fm["tags"] == ["python", "cli"]

    def test_body_excludes_frontmatter(self) -> None:
        _, body = parse_frontmatter(FULL_FRONTMATTER)
        assert "# Title" in body
        assert "Body text here." in body
        assert "project:" not in body

    def test_no_frontmatter_returns_empty_dict(self) -> None:
        fm, body = parse_frontmatter(NO_FRONTMATTER)
        assert fm == {}
        assert "No frontmatter" in body

    def test_unclosed_block_returns_empty_dict(self) -> None:
        fm, body = parse_frontmatter(UNCLOSED_FRONTMATTER)
        assert fm == {}
        assert "project: orphan" in body

    def test_empty_string(self) -> None:
        fm, body = parse_frontmatter("")
        assert fm == {}
        assert body == ""

    def test_lines_without_colon_are_skipped(self) -> None:
        text = "---\nproject: x\nthis line has no colon\n---\nbody"
        fm, _ = parse_frontmatter(text)
        assert fm["project"] == "x"
        assert "this line has no colon" not in fm

    def test_value_with_colon_preserves_remainder(self) -> None:
        # Values that themselves contain colons should keep everything after
        # the first colon (partition behaviour).
        text = "---\ndate: 2026-01-15T10:00:00\n---\nbody"
        fm, _ = parse_frontmatter(text)
        assert fm["date"] == "2026-01-15T10:00:00"

    def test_body_stripped_of_leading_blank_lines(self) -> None:
        fm, body = parse_frontmatter(FULL_FRONTMATTER)
        assert not body.startswith("\n")


# ---------------------------------------------------------------------------
# load_note  (uses real files via tmp_path)
# ---------------------------------------------------------------------------


@pytest.fixture()
def note_file(tmp_path: Path) -> Path:
    content = """\
---
project: demo
tags: [Python, CLI]
category: tools
status: active
date: 2026-01-15
---

# Demo note

Some body text [[other-note]].
"""
    p = tmp_path / "2026-01-15-demo.md"
    p.write_text(content, encoding="utf-8")
    return p


class TestLoadNote:
    def test_scalar_fields(self, note_file: Path) -> None:
        note = load_note(note_file)
        assert note.project == "demo"
        assert note.category == "tools"
        assert note.status == "active"
        assert note.date == "2026-01-15"

    def test_tags_lowercased(self, note_file: Path) -> None:
        note = load_note(note_file)
        assert note.tags == ["python", "cli"]

    def test_body_present(self, note_file: Path) -> None:
        note = load_note(note_file)
        assert "Some body text" in note.body

    def test_path_preserved(self, note_file: Path) -> None:
        note = load_note(note_file)
        assert note.path == note_file

    def test_missing_fields_are_none(self, tmp_path: Path) -> None:
        content = "---\nstatus: draft\n---\nbody"
        p = tmp_path / "minimal.md"
        p.write_text(content, encoding="utf-8")
        note = load_note(p)
        assert note.project is None
        assert note.category is None
        assert note.date is None
        assert note.tags == []

    def test_tags_as_scalar_string(self, tmp_path: Path) -> None:
        content = "---\ntags: python\n---\nbody"
        p = tmp_path / "scalar-tag.md"
        p.write_text(content, encoding="utf-8")
        note = load_note(p)
        assert note.tags == ["python"]

    def test_no_frontmatter_note(self, tmp_path: Path) -> None:
        content = "# Just a heading\n\nPlain body."
        p = tmp_path / "plain.md"
        p.write_text(content, encoding="utf-8")
        note = load_note(p)
        assert note.project is None
        assert note.tags == []
        assert "Plain body" in note.body


# ---------------------------------------------------------------------------
# _fuzzy_contains
# ---------------------------------------------------------------------------


class TestFuzzyContains:
    def test_exact_match(self) -> None:
        assert _fuzzy_contains({"python", "cli"}, "python")

    def test_near_miss_within_cutoff(self) -> None:
        # "pytohn" is one transposition away from "python"
        assert _fuzzy_contains({"python"}, "pytohn")

    def test_near_miss_outside_cutoff(self) -> None:
        # "xyz" has no near match in {"python"}
        assert not _fuzzy_contains({"python"}, "xyz")

    def test_empty_body_words(self) -> None:
        assert not _fuzzy_contains(set(), "python")

    def test_custom_cutoff_stricter(self) -> None:
        # At cutoff=0.99, only exact matches should pass
        assert not _fuzzy_contains({"python"}, "pytohn", cutoff=0.99)
        assert _fuzzy_contains({"python"}, "python", cutoff=0.99)


# ---------------------------------------------------------------------------
# fuzzy_text_match
# ---------------------------------------------------------------------------


class TestFuzzyTextMatch:
    def test_all_words_exact(self) -> None:
        assert fuzzy_text_match("python is great", "python great")

    def test_all_words_fuzzy(self) -> None:
        # "pytohn" is a typo for "python"
        assert fuzzy_text_match("python is great", "pytohn")

    def test_missing_word_returns_false(self) -> None:
        assert not fuzzy_text_match("python is great", "python rust")

    def test_empty_query_returns_true(self) -> None:
        assert fuzzy_text_match("anything here", "")

    def test_case_insensitive(self) -> None:
        assert fuzzy_text_match("Python CLI", "python cli")

    def test_multi_word_all_must_match(self) -> None:
        assert fuzzy_text_match("fast cli tool", "fast tool")
        assert not fuzzy_text_match("fast cli tool", "fast database")


# ---------------------------------------------------------------------------
# text_match
# ---------------------------------------------------------------------------


class TestTextMatch:
    def test_exact_substring_match(self) -> None:
        assert text_match("Hello world", "world", fuzzy=False)

    def test_exact_case_insensitive(self) -> None:
        assert text_match("Hello World", "hello", fuzzy=False)

    def test_no_match_fuzzy_false(self) -> None:
        assert not text_match("python rocks", "rubby", fuzzy=False)

    def test_typo_match_fuzzy_true(self) -> None:
        assert text_match("python rocks", "pytohn", fuzzy=True)

    def test_no_match_even_with_fuzzy(self) -> None:
        assert not text_match("python rocks", "javascript database", fuzzy=True)


# ---------------------------------------------------------------------------
# extract_links
# ---------------------------------------------------------------------------


class TestExtractLinks:
    def test_no_links(self) -> None:
        assert extract_links("No wikilinks here.") == []

    def test_single_link(self) -> None:
        assert extract_links("See [[my-note]] for details.") == ["my-note"]

    def test_multiple_links(self) -> None:
        result = extract_links("[[note-a]] and [[note-b]] and [[note-c]]")
        assert result == ["note-a", "note-b", "note-c"]

    def test_duplicate_links_both_returned(self) -> None:
        # extract_links returns raw occurrences; dedup is the caller's job
        result = extract_links("[[foo]] then [[foo]] again")
        assert result == ["foo", "foo"]

    def test_single_bracket_not_matched(self) -> None:
        assert extract_links("[not a wikilink]") == []

    def test_unclosed_bracket_not_matched(self) -> None:
        assert extract_links("[[unclosed") == []

    def test_link_with_spaces(self) -> None:
        # spaces inside brackets are valid if present
        result = extract_links("[[my note title]]")
        assert result == ["my note title"]


# ---------------------------------------------------------------------------
# build_backlink_index
# ---------------------------------------------------------------------------


def _make_note(stem: str, body: str, tmp_path: Path) -> Note:
    p = tmp_path / f"{stem}.md"
    p.write_text(f"---\nstatus: active\n---\n{body}", encoding="utf-8")
    return load_note(p)


class TestBuildBacklinkIndex:
    def test_single_link(self, tmp_path: Path) -> None:
        a = _make_note("note-a", "References [[note-b]].", tmp_path)
        b = _make_note("note-b", "No outbound links.", tmp_path)
        index = build_backlink_index([a, b])
        assert index.get("note-b") == ["note-a"]
        assert "note-a" not in index

    def test_mutual_links(self, tmp_path: Path) -> None:
        a = _make_note("note-a", "See [[note-b]].", tmp_path)
        b = _make_note("note-b", "See [[note-a]].", tmp_path)
        index = build_backlink_index([a, b])
        assert index["note-a"] == ["note-b"]
        assert index["note-b"] == ["note-a"]

    def test_duplicate_link_in_same_note_counted_once(self, tmp_path: Path) -> None:
        # A note mentioning [[target]] twice should still produce one backlink
        a = _make_note("note-a", "See [[target]] and [[target]] again.", tmp_path)
        index = build_backlink_index([a])
        assert index["target"] == ["note-a"]

    def test_link_to_nonexistent_note_still_indexed(self, tmp_path: Path) -> None:
        a = _make_note("note-a", "See [[ghost-note]].", tmp_path)
        index = build_backlink_index([a])
        assert "ghost-note" in index

    def test_no_notes(self) -> None:
        assert build_backlink_index([]) == {}

    def test_multiple_inbound_links(self, tmp_path: Path) -> None:
        a = _make_note("note-a", "See [[shared]].", tmp_path)
        b = _make_note("note-b", "Also see [[shared]].", tmp_path)
        index = build_backlink_index([a, b])
        assert sorted(index["shared"]) == ["note-a", "note-b"]


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


class TestSlugify:
    def test_basic_title(self) -> None:
        assert slugify("Hello World") == "hello-world"

    def test_special_chars_replaced(self) -> None:
        # "++" becomes "--" then collapses to "-"; trailing "!" stripped
        assert slugify("C++ Notes!") == "c-notes"

    def test_consecutive_dashes_collapsed(self) -> None:
        # Multiple non-alnum chars in a row collapse to a single dash
        result = slugify("foo  bar")
        assert "--" not in result
        assert result == "foo--bar".replace("--", "-")

    def test_leading_trailing_dashes_stripped(self) -> None:
        result = slugify("  leading")
        assert not result.startswith("-")

    def test_all_lowercase(self) -> None:
        assert slugify("UPPER") == "upper"

    def test_numbers_preserved(self) -> None:
        assert slugify("Note 42") == "note-42"


# ---------------------------------------------------------------------------
# new_note_path
# ---------------------------------------------------------------------------


class TestNewNotePath:
    def test_explicit_date(self, tmp_path: Path) -> None:
        on = date(2026, 3, 15)
        path = new_note_path(tmp_path, "My Note", on=on)
        assert path == tmp_path / "notes" / "2026-03-15-my-note.md"

    def test_uses_today_when_no_date(self, tmp_path: Path) -> None:
        path = new_note_path(tmp_path, "Today Note")
        expected_prefix = date.today().isoformat()
        assert path.name.startswith(expected_prefix)

    def test_path_inside_notes_subdir(self, tmp_path: Path) -> None:
        path = new_note_path(tmp_path, "Test", on=date(2026, 1, 1))
        assert path.parent == tmp_path / "notes"


# ---------------------------------------------------------------------------
# render_note
# ---------------------------------------------------------------------------


class TestRenderNote:
    def test_contains_all_fields(self) -> None:
        rendered = render_note(
            title="My Note",
            project="my-project",
            tags=["python", "cli"],
            category="dev",
            status="active",
            on=date(2026, 1, 15),
        )
        assert "project: my-project" in rendered
        assert "tags: [python, cli]" in rendered
        assert "category: dev" in rendered
        assert "status: active" in rendered
        assert "date: 2026-01-15" in rendered
        assert "# My Note" in rendered

    def test_empty_project_and_category(self) -> None:
        rendered = render_note(
            title="Minimal",
            project=None,
            tags=[],
            category=None,
            status="draft",
            on=date(2026, 1, 1),
        )
        assert "project: \n" in rendered
        assert "category: \n" in rendered
        assert "tags: []" in rendered

    def test_starts_and_ends_with_frontmatter_delimiters(self) -> None:
        rendered = render_note("T", None, [], None, "draft", on=date(2026, 1, 1))
        assert rendered.startswith("---\n")
        assert "---\n" in rendered[4:]  # closing delimiter present


# ---------------------------------------------------------------------------
# matches  (filter logic)
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_note(tmp_path: Path) -> Note:
    content = """\
---
project: backend
tags: [python, api]
category: dev
status: active
date: 2026-01-15
---

Discusses database and caching strategies.
"""
    p = tmp_path / "2026-01-15-backend.md"
    p.write_text(content, encoding="utf-8")
    return load_note(p)


class TestMatches:
    def test_no_filters_always_matches(self, sample_note: Note) -> None:
        assert matches(sample_note)

    def test_exact_project_match(self, sample_note: Note) -> None:
        assert matches(sample_note, project="backend")

    def test_wrong_project_no_match(self, sample_note: Note) -> None:
        assert not matches(sample_note, project="frontend")

    def test_exact_tag_match(self, sample_note: Note) -> None:
        assert matches(sample_note, tag="python")

    def test_wrong_tag_no_match(self, sample_note: Note) -> None:
        assert not matches(sample_note, tag="rust")

    def test_exact_category_match(self, sample_note: Note) -> None:
        assert matches(sample_note, category="dev")

    def test_wrong_category_no_match(self, sample_note: Note) -> None:
        assert not matches(sample_note, category="ops")

    def test_status_match(self, sample_note: Note) -> None:
        assert matches(sample_note, status="active")

    def test_wrong_status_no_match(self, sample_note: Note) -> None:
        assert not matches(sample_note, status="archived")

    def test_text_match(self, sample_note: Note) -> None:
        assert matches(sample_note, text="database")

    def test_text_no_match(self, sample_note: Note) -> None:
        assert not matches(sample_note, text="kubernetes")

    def test_fuzzy_project_match(self, sample_note: Note) -> None:
        # "backand" is a typo for "backend"
        assert matches(sample_note, project="backand", fuzzy=True)

    def test_fuzzy_tag_match(self, sample_note: Note) -> None:
        assert matches(sample_note, tag="pytohn", fuzzy=True)

    def test_fuzzy_text_match(self, sample_note: Note) -> None:
        assert matches(sample_note, text="databse", fuzzy=True)

    def test_multiple_filters_all_must_pass(self, sample_note: Note) -> None:
        assert matches(sample_note, project="backend", tag="python", status="active")
        assert not matches(sample_note, project="backend", tag="rust")

    def test_note_with_no_project_fails_project_filter(self, tmp_path: Path) -> None:
        p = tmp_path / "no-project.md"
        p.write_text("---\nstatus: draft\n---\nbody", encoding="utf-8")
        note = load_note(p)
        assert not matches(note, project="something")
