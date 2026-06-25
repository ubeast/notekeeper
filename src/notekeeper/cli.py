"""Command-line interface for notekeeper.

Subcommands:
    nk search   --project/--tag/--category/--status/--text
    nk new      "Title" --project P --tags a,b --category reference
    nk validate

Installed as the `nk` console script via pyproject.toml, so it runs
as a plain command after `pip install -e .` rather than `python3 some/path.py`.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from notekeeper.notes import (
    Note,
    build_backlink_index,
    extract_links,
    iter_notes,
    matches,
    new_note_path,
    render_note,
)
from notekeeper.vocabulary import load_vocabulary, validate


def _root_dir(args: argparse.Namespace) -> Path:
    """Resolve the notes root: explicit --root flag, else current directory."""
    return args.root if args.root else Path.cwd()


def _print_results(results: list[Note]) -> None:
    if not results:
        print("No matching notes.")
        return
    for note in results:
        print(note.path.name)
        print(
            f"  project={note.project or '-'} "
            f"category={note.category or '-'} "
            f"status={note.status or '-'} "
            f"tags={','.join(note.tags) or '-'}"
        )


def cmd_search(args: argparse.Namespace) -> None:
    """Run the search subcommand and print matches."""
    notes = iter_notes(_root_dir(args))
    results = [
        note
        for note in notes
        if matches(
            note, args.project, args.tag, args.category, args.status, args.text, args.fuzzy
        )
    ]
    _print_results(results)


def cmd_new(args: argparse.Namespace) -> None:
    """Scaffold a new note file with frontmatter pre-filled, ready to edit."""
    root_dir = _root_dir(args)
    tags = [tag.strip() for tag in args.tags.split(",")] if args.tags else []
    path = new_note_path(root_dir, args.title)
    if path.exists():
        print(f"Note already exists: {path}")
        return
    content = render_note(args.title, args.project, tags, args.category, args.status)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Created: {path}")


def cmd_validate(args: argparse.Namespace) -> None:
    """Check every note's frontmatter against TAGS.md and print warnings."""
    root_dir = _root_dir(args)
    notes = iter_notes(root_dir)
    vocabulary = load_vocabulary(root_dir)
    warnings = validate(notes, vocabulary)
    if not warnings:
        print(f"All {len(notes)} notes valid.")
        return
    for warning in warnings:
        print(f"WARNING: {warning}")


def cmd_links(args: argparse.Namespace) -> None:
    """Show outgoing links and incoming backlinks for a given note stem."""
    root_dir = _root_dir(args)
    notes = iter_notes(root_dir)
    target_note = next((note for note in notes if note.path.stem == args.note), None)
    if target_note is None:
        print(f"No note found with stem '{args.note}'.")
        return

    outgoing = extract_links(target_note.body)
    print("Links to:")
    print("\n".join(f"  {link}" for link in outgoing) if outgoing else "  (none)")

    backlinks = build_backlink_index(notes).get(args.note, [])
    print("Linked from:")
    print("\n".join(f"  {stem}" for stem in backlinks) if backlinks else "  (none)")



def main() -> None:
    """Parse arguments and dispatch to the selected subcommand."""
    parser = argparse.ArgumentParser(prog="nk", description="Personal markdown knowledge base.")
    parser.add_argument(
        "--root", type=Path, default=None, help="Notes root directory (default: cwd)."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search notes by field and/or text.")
    search_parser.add_argument("--project", type=str, default=None)
    search_parser.add_argument("--tag", type=str, default=None)
    search_parser.add_argument("--category", type=str, default=None)
    search_parser.add_argument("--status", type=str, default=None)
    search_parser.add_argument("--text", type=str, default=None)
    search_parser.add_argument(
        "--fuzzy",
        action="store_true",
        help="Tolerate typos/near-misses in project, tag, category, and text.",
    )
    search_parser.set_defaults(func=cmd_search)

    new_parser = subparsers.add_parser("new", help="Create a new note with frontmatter filled in.")
    new_parser.add_argument("title", type=str)
    new_parser.add_argument("--project", type=str, default=None)
    new_parser.add_argument("--tags", type=str, default=None, help="Comma-separated.")
    new_parser.add_argument("--category", type=str, default=None)
    new_parser.add_argument("--status", type=str, default="active")
    new_parser.set_defaults(func=cmd_new)

    validate_parser = subparsers.add_parser(
        "validate", help="Check notes against TAGS.md controlled vocabulary."
    )
    validate_parser.set_defaults(func=cmd_validate)

    links_parser = subparsers.add_parser(
        "links", help="Show outgoing links and incoming backlinks for a note."
    )
    links_parser.add_argument("note", type=str, help="Note filename stem (no .md).")
    links_parser.set_defaults(func=cmd_links)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
