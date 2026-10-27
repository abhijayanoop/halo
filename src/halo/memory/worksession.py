"""What to work on: read the project notes and today's journal, and propose up to three tasks.

No model is involved. The answer is built straight from the user's own notes, so it is
instant, free, and nothing in a note can reach a prompt. Sources, in order: unfinished
work from a project's `last_stop`, today's journal checkboxes, then open checkboxes in
the project notes. Only notes inside the vault are read (a link out of it is refused), and
the Inbox of proposed memories is never a source: text from the web or an agent must not
turn into a task.
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

from halo.memory.vault import VaultPathError, resolve_note

log = logging.getLogger(__name__)

MAX_PROPOSALS = 3
MAX_TITLE = 120
UNFINISHED = {"kept", "failed"}  # a session that left work behind

Source = Literal["last_stop", "journal", "project"]

_FRONTMATTER = re.compile(r"\A---\r?\n(?P<front>.*?)\r?\n---\r?\n", re.DOTALL)
_CHECKBOX = re.compile(r"^\s*[-*]\s+\[ \]\s+(?P<text>.+?)\s*$")
_INLINE_FIELD = re.compile(r"\[[^\]]*::[^\]]*\]")
_BLOCK_ID = re.compile(r"\s\^[A-Za-z0-9-]+\s*$")
_LAST_STOP = re.compile(
    r"^(?P<day>\d{4}-\d{2}-\d{2}):\s*(?:(?P<outcome>merged|discarded|kept|denied|failed):\s*)?(?P<text>.*)$"
)


@dataclass(frozen=True)
class Proposal:
    title: str
    project: str | None
    request: str  # what to send to Halo to start it
    source: Source


@dataclass(frozen=True)
class WorkPlan:
    stopped_at: str = ""
    project: str | None = None
    proposals: list[Proposal] = field(default_factory=list)


@dataclass(frozen=True)
class _Note:
    name: str
    fields: dict[str, str]
    body: str


def _read(vault: Path, relative: str, name: str) -> _Note | None:
    """A note inside the vault, or None if it is missing, unreadable or outside it."""
    try:
        text = resolve_note(vault, relative).read_text(encoding="utf-8")
    except (VaultPathError, OSError, ValueError):
        return None
    fields: dict[str, str] = {}
    body = text
    match = _FRONTMATTER.match(text)
    if match:
        body = text[match.end() :]
        for line in match.group("front").splitlines():
            key, sep, value = line.partition(":")
            if sep:
                fields[key.strip()] = value.strip().strip("\"'")
    return _Note(name, fields, body)


def _title(raw: str) -> str:
    text = _INLINE_FIELD.sub("", raw)
    text = _BLOCK_ID.sub("", text)
    return " ".join(text.split())[:MAX_TITLE]


def _checkboxes(body: str) -> list[str]:
    found = []
    for line in body.splitlines():
        match = _CHECKBOX.match(line)
        if match and (title := _title(match.group("text"))):
            found.append(title)
    return found


def _parse_last_stop(raw: str) -> tuple[str, str, str]:
    """(day, outcome, text) of a `last_stop` such as '2026-10-27: kept: Add a thing'."""
    match = _LAST_STOP.match(raw.strip())
    if not match:
        return "", "", raw.strip()
    return match["day"], match["outcome"] or "", match["text"].strip()


def _projects(vault: Path) -> list[_Note]:
    folder = vault / "Projects"
    if not folder.is_dir():
        return []
    notes = []
    for path in sorted(folder.glob("*.md")):
        note = _read(vault, f"Projects/{path.name}", path.stem)
        if note is not None:
            notes.append(note)
    # Newest last_stop first; notes that never recorded one come last, by name.
    notes.sort(
        key=lambda n: (_parse_last_stop(n.fields.get("last_stop", ""))[0], n.name),
        reverse=True,
    )
    return notes


def plan_work(vault: Path, today: date, limit: int = MAX_PROPOSALS) -> WorkPlan:
    projects = _projects(vault)
    stopped_at = ""
    stopped_project: str | None = None
    proposals: list[Proposal] = []
    seen: set[str] = set()

    def add(title: str, project: str | None, request: str, source: Source) -> None:
        key = title.casefold()
        if key not in seen and len(proposals) < limit:
            seen.add(key)
            proposals.append(Proposal(title, project, request, source))

    for note in projects:
        day, outcome, text = _parse_last_stop(note.fields.get("last_stop", ""))
        if not text:
            continue
        if not stopped_at:
            stopped_project = note.name
            tag = ", ".join(part for part in (outcome, day) if part)
            stopped_at = f"{text} ({tag})" if tag else text
        if outcome in UNFINISHED:
            add(f"Continue: {text}", note.name, f"{text} in {note.name}", "last_stop")

    journal = _read(vault, f"Journal/{today.isoformat()}.md", "journal")
    if journal is not None:
        for title in _checkboxes(journal.body):
            add(title, None, title, "journal")

    for note in projects:
        for title in _checkboxes(note.body):
            add(title, note.name, f"{title} in {note.name}", "project")

    return WorkPlan(stopped_at, stopped_project, proposals)
