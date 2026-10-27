"""A SQLite index over the memories in a vault: one table of items and an FTS5
table for keyword search. The notes stay the source of truth; this is rebuilt
from them, so a line deleted in Obsidian is forgotten on the next re-index.
"""

import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from halo.core.contracts import MemoryItem
from halo.memory.vault import parse_note

# Words that say nothing about which memory is meant.
_STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "of",
        "for",
        "to",
        "and",
        "or",
        "in",
        "on",
        "at",
        "is",
        "are",
        "was",
        "were",
        "did",
        "do",
        "does",
        "i",
        "me",
        "my",
        "what",
        "which",
        "who",
        "how",
        "about",
        "with",
        "that",
        "this",
        "it",
        "you",
        "your",
        "have",
        "has",
        "had",
        "be",
        "been",
        "by",
        "from",
        "as",
    ]
)
# Notes Halo itself writes or Obsidian owns: never read as memories.
_SKIPPED_FOLDERS = {"inbox"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    note_path TEXT NOT NULL,
    block_id TEXT NOT NULL,
    fact TEXT NOT NULL,
    source TEXT NOT NULL,
    trust TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    superseded INTEGER NOT NULL,
    privacy TEXT NOT NULL,
    PRIMARY KEY (note_path, block_id)
);
CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    fact, note_path UNINDEXED, block_id UNINDEXED, tokenize = 'porter unicode61'
);
"""


def query_words(text: str) -> list[str]:
    """The meaningful words of a question, lower-cased, in order, without repeats."""
    words = re.findall(r"[^\W_]+", text.lower())
    return [w for w in dict.fromkeys(words) if w not in _STOPWORDS]


def _match_query(text: str) -> str:
    """An FTS5 query that finds any of the meaningful words. Every word is quoted,
    so nothing a user types can be read as FTS syntax."""
    return " OR ".join(f'"{w}"' for w in query_words(text))


def _item(row: sqlite3.Row | tuple) -> MemoryItem:
    note_path, block_id, fact, source, trust, created, expires, sup, privacy = row
    return MemoryItem(
        fact=fact,
        source=source,
        trust=trust,
        created_at=datetime.fromisoformat(created),
        expires_at=datetime.fromisoformat(expires) if expires else None,
        block_id=block_id,
        note_path=note_path,
        superseded=bool(sup),
        privacy=privacy,
    )


class MemoryIndex:
    def __init__(self, db_path: Path | str, vault: Path) -> None:
        self._vault = vault
        self._lock = threading.RLock()
        if str(db_path) != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(db_path), check_same_thread=False)
        with self._lock:
            self._db.executescript(_SCHEMA)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    # -- keeping the index in step with the notes ---------------------------------

    def reindex_note(self, path: Path) -> int:
        """Replace everything indexed from this note with what it says now."""
        relative = path.resolve().relative_to(self._vault.resolve()).as_posix()
        items = parse_note(path, self._vault)
        with self._lock, self._db:
            self._drop(relative)
            for item in items:
                self._db.execute(
                    "INSERT OR REPLACE INTO items VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        item.note_path,
                        item.block_id,
                        item.fact,
                        item.source,
                        item.trust,
                        item.created_at.isoformat(),
                        item.expires_at.isoformat() if item.expires_at else None,
                        int(item.superseded),
                        item.privacy,
                    ),
                )
                self._db.execute(
                    "INSERT INTO items_fts (fact, note_path, block_id) VALUES (?,?,?)",
                    (item.fact, item.note_path, item.block_id),
                )
        return len(items)

    def remove_note(self, relative: str) -> None:
        with self._lock, self._db:
            self._drop(relative)

    def _drop(self, relative: str) -> None:
        self._db.execute("DELETE FROM items WHERE note_path = ?", (relative,))
        self._db.execute("DELETE FROM items_fts WHERE note_path = ?", (relative,))

    def vault_notes(self) -> list[Path]:
        """Every note that can hold memories: Markdown outside hidden folders
        (like .obsidian) and Halo's own inbox."""
        found = []
        for path in sorted(self._vault.rglob("*.md")):
            parts = path.relative_to(self._vault).parts
            if any(p.startswith(".") for p in parts):
                continue
            if parts[0].lower() in _SKIPPED_FOLDERS and len(parts) > 1:
                continue
            found.append(path)
        return found

    def reindex_all(self) -> int:
        """Index every note, and forget notes that no longer exist."""
        notes = self.vault_notes()
        present = {p.relative_to(self._vault).as_posix() for p in notes}
        with self._lock:
            known = {
                row[0]
                for row in self._db.execute("SELECT DISTINCT note_path FROM items")
            }
        for relative in known - present:
            self.remove_note(relative)
        return sum(self.reindex_note(path) for path in notes)

    # -- reading ------------------------------------------------------------------

    def search(self, query: str, limit: int = 20) -> list[MemoryItem]:
        """Items that match at least half of the meaningful words of `query`
        (rounded up), best match first. One stray word is not an answer: a
        question about the "HUD window" should not return a line that only says
        "Windows"."""
        words = query_words(query)
        if not words:
            return []
        needed = -(-len(words) // 2)  # half, rounded up
        with self._lock:
            rows = self._db.execute(
                "SELECT i.note_path, i.block_id, i.fact, i.source, i.trust, i.created_at,"
                " i.expires_at, i.superseded, i.privacy"
                " FROM items_fts f JOIN items i"
                "   ON i.note_path = f.note_path AND i.block_id = f.block_id"
                " WHERE items_fts MATCH ? ORDER BY bm25(items_fts) LIMIT ?",
                (_match_query(query), max(limit * 5, 50)),
            ).fetchall()
            hits: dict[tuple[str, str], int] = {}
            if needed > 1:
                # How many of the words each item contains, counted with the same
                # stemmed tokenizer the index uses, so "picked" matches "pick".
                for word in words:
                    found = self._db.execute(
                        "SELECT note_path, block_id FROM items_fts WHERE items_fts MATCH ?",
                        (f'"{word}"',),
                    ).fetchall()
                    for key in found:
                        hits[(key[0], key[1])] = hits.get((key[0], key[1]), 0) + 1
        kept = [
            row
            for row in rows
            if needed <= 1 or hits.get((row[0], row[1]), 0) >= needed
        ]
        return [_item(row) for row in kept[:limit]]

    def items(self) -> list[MemoryItem]:
        with self._lock:
            rows = self._db.execute(
                "SELECT note_path, block_id, fact, source, trust, created_at, expires_at,"
                " superseded, privacy FROM items ORDER BY note_path, rowid"
            ).fetchall()
        return [_item(row) for row in rows]
