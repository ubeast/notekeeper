# notekeeper

A personal markdown knowledge base: search, capture, and validate notes
by project, tag, category, or text. Installable as a real `nk` command,
not a script you remember to invoke with `python3`.

## Install

```bash
cd notekeeper
uv tool install --editable .
```

`nk` is now available as a command anywhere on your machine — `uv tool
install` is uv's equivalent of pipx: an isolated environment, exposed as
a global command. `--editable` means code edits take effect immediately,
no reinstall needed.

If you'd rather keep it inside one project's own virtual environment
instead of installing it globally, use `uv pip install -e .` in that
project's venv instead.

## The repo-vs-notes rule

One rule, not a per-project decision:

> **Would a stranger who clones just this one repo need this file to
> understand or maintain the code?**
> - Yes → put it in that repo's own `docs/` or README.
> - No → put it in your private notes repo (see the companion repo,
>   `field_notes` or whatever you named yours).

Code-essential docs travel with the code. Everything else — reasoning,
decisions driven by your priorities rather than the code, cross-project
patterns, non-code life threads — lives in one searchable place. A note
about a specific repo just gets `project: that-repo-name` in its
frontmatter; it doesn't need to physically live inside that repo.

This repo (`notekeeper`) is the tool only — generic code, no personal
content. Your actual notes belong in a separate, private repo.

## Commands

```bash
# Search — combine any flags, they AND together
nk search --project my_project
nk search --tag performance --category decision
nk search --text "switched to OLS"

# Fuzzy search — tolerates typos and near-misses on project/tag/category/text
nk search --text "switced to OLS" --fuzzy
nk search --tag confg --fuzzy   # matches 'configuration'

# Create — scaffolds frontmatter so writing a note is one line, not a
# template you retype. This is the friction-killer: low friction is
# what keeps a system like this alive past week one.
nk new "Why I switched to OLS for trend detection" \
    --project my_project --tags python,architecture --category decision

# Validate — catches tag/project/category sprawl (e.g. 'claude' vs
# 'claude-config' vs 'claude_workflow' silently becoming three tags)
nk validate

# Links — outgoing links and incoming backlinks for a note. Use [[note-stem]]
# in a note's body to reference another note (no .md, no path) — only when
# there's a real connection worth recording, not on every note.
nk links 2026-06-25-some-note-stem
```

## Note format

```markdown
---
project: my_project
tags: [python, architecture]
category: decision
status: active
date: 2026-06-25
---

# Title

Body content in normal markdown.
```

See `TAGS.example.md` for the controlled-vocabulary schema — copy it to
`TAGS.md` in your own notes repo and fill in your real projects (this
template stays generic since real project names belong in your private
notes repo, not this public one).

## Layout

```
notekeeper/
├── pyproject.toml
├── TAGS.example.md
├── README.md
├── LICENSE
├── .gitignore
├── src/notekeeper/
│   ├── __init__.py
│   ├── notes.py        <- parsing, filtering, note creation, backlinks
│   ├── vocabulary.py    <- TAGS.md loading and validation
│   └── cli.py           <- search / new / validate / links subcommands
└── notes/.gitkeep       <- empty; this repo holds no real content
```

## What this deliberately doesn't do (yet)

- No indexing — a full directory scan per search is instant at personal
  scale. If the notes collection grows past a few thousand files, load
  the same frontmatter fields into SQLite instead of rewriting this.

## Tasks vs. notes

Tasks (open todos, due dates) have a different lifecycle than notes
(decisions, reference, reasoning) — don't force them into this format.
Keep a separate `TASKS.md` checklist for open todos; use notes for
things worth remembering *why*.
