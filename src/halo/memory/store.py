"""The one door to memory: a vault of notes, an index over it, and an inbox of
proposals. Skills, the app and the privacy guard all go through this.

Everything here is blocking (files and SQLite). Callers on the event loop wrap
calls in `asyncio.to_thread`.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from halo.core.contracts import (
    MemoryCandidate,
    MemoryItem,
    MemorySource,
    TrustLevel,
)
from halo.memory.index import MemoryIndex, query_words
from halo.memory.proposals import append_proposal, list_proposals
from halo.memory.retrieve import DEFAULT_BUDGET, Context, assemble_context, retrieve
from halo.memory.vault import (
    VaultPathError,
    append_memory,
    delete_memory,
    ensure_vault,
    note_privacy,
    obsidian_link,
    resolve_note,
)

INBOX = "Inbox/proposed-memories.md"
DEFAULT_NOTE = "Profile.md"
SIMILAR = 0.8  # word overlap at which two facts count as the same one


def _words(text: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", text.lower()))


def similar(a: str, b: str) -> bool:
    """True if two facts say (nearly) the same thing, by word overlap."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / len(wa | wb) >= SIMILAR


@dataclass(frozen=True)
class Proposal:
    id: str
    candidate: MemoryCandidate


class MemoryStore:
    def __init__(
        self,
        vault: Path,
        db_path: Path,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.vault = vault
        self._db_path = db_path
        self._clock = clock
        self._index: MemoryIndex | None = None

    @property
    def index(self) -> MemoryIndex:
        if self._index is None:
            raise RuntimeError("the memory store is not started")
        return self._index

    def start(self) -> None:
        """Create the vault the first time, open the index and read every note."""
        ensure_vault(self.vault)
        self._index = MemoryIndex(self._db_path, self.vault)
        self._index.reindex_all()

    def close(self) -> None:
        if self._index is not None:
            self._index.close()
            self._index = None

    # -- keeping the index in step with notes edited elsewhere (Obsidian) --------

    def reindex_note(self, path: Path) -> None:
        self.index.reindex_note(path)

    def remove_note(self, relative: str) -> None:
        self.index.remove_note(relative)

    # -- remember, recall, forget --------------------------------------------------

    def remember(
        self,
        fact: str,
        *,
        note: str = DEFAULT_NOTE,
        source: MemorySource = "you",
        trust: TrustLevel = "high",
    ) -> MemoryItem:
        """Write a fact to a note straight away, with where it came from."""
        if not note.lower().endswith(".md"):
            raise VaultPathError(f"a note must be a .md file: {note!r}")
        path = resolve_note(self.vault, note)
        item = append_memory(
            path, self.vault, fact, source=source, trust=trust, now=self._clock()
        )
        self.index.reindex_note(path)
        return item

    def recall(self, query: str, *, limit: int = 5) -> list[MemoryItem]:
        """Memories for the user to read on their own screen. Local notes are
        included here: this never goes to a model."""
        return retrieve(self.index, query, now=self._clock())[:limit]

    def context(self, query: str, *, budget: int = DEFAULT_BUDGET) -> Context:
        """The memory section for a cloud prompt: `privacy: local` is left out."""
        found = retrieve(self.index, query, now=self._clock())
        return assemble_context(found, budget=budget)

    def forget(self, query: str, *, max_items: int = 3) -> list[MemoryItem]:
        """Delete the memories whose text contains every meaningful word of
        `query`, at most `max_items` of them. Anything vaguer deletes nothing."""
        words = query_words(query)
        if not words:
            return []
        gone: list[MemoryItem] = []
        for item in self.index.search(query, limit=50):
            if len(gone) >= max_items:
                break
            if not all(w in item.fact.lower() for w in words):
                continue
            path = resolve_note(self.vault, item.note_path)
            if delete_memory(path, item.block_id):
                gone.append(item)
                self.index.reindex_note(path)
        return gone

    def link(self, item: MemoryItem) -> str:
        return obsidian_link(self.vault, item.note_path)

    def local_texts(self) -> list[str]:
        """The full text of every `privacy: local` note, for the guard that stops
        it from reaching a cloud prompt."""
        texts = []
        for path in self.index.vault_notes():
            if note_privacy(path) == "local":
                try:
                    texts.append(path.read_bytes().decode("utf-8"))
                except OSError:
                    continue
        return texts

    # -- proposed memories -----------------------------------------------------------

    def _inbox(self) -> Path:
        return resolve_note(self.vault, INBOX)

    def proposals(self) -> list[Proposal]:
        return [Proposal(pid, c) for pid, c in list_proposals(self._inbox())]

    def propose(self, candidate: MemoryCandidate) -> str | None:
        """List a candidate for the user to approve. None if the same fact is
        already remembered or already waiting."""
        known = [i.fact for i in self.index.items()]
        known += [p.candidate.fact for p in self.proposals()]
        if any(similar(candidate.fact, fact) for fact in known):
            return None
        return append_proposal(self._inbox(), candidate, self._clock())

    def _note_for(self, subject: str) -> str:
        """The note named like the subject (Projects/halo.md for "halo"), else the profile."""
        wanted = subject.strip().lower()
        if wanted:
            for path in self.index.vault_notes():
                if path.stem.lower() == wanted:
                    return path.relative_to(self.vault).as_posix()
        return DEFAULT_NOTE

    def approve(self, proposal_id: str, *, note: str | None = None) -> MemoryItem:
        """Write a proposal to a real note and remove it from the inbox."""
        found = next((p for p in self.proposals() if p.id == proposal_id), None)
        if found is None:
            raise KeyError(proposal_id)
        item = self.remember(
            found.candidate.fact,
            note=note or self._note_for(found.candidate.subject),
            source=found.candidate.source,
            trust=found.candidate.trust,
        )
        delete_memory(self._inbox(), proposal_id)
        return item

    def reject(self, proposal_id: str) -> bool:
        return delete_memory(self._inbox(), proposal_id)
