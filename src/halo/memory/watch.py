"""Keep the index in step with notes edited outside Halo (Obsidian, an editor).

A line deleted in Obsidian is forgotten as soon as the file is saved: the
watcher re-reads that one note. Hidden folders (.obsidian) and Halo's inbox are
ignored, the same as when the whole vault is indexed.
"""

import logging
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver

from halo.memory.store import MemoryStore

logger = logging.getLogger(__name__)


class VaultWatcher(FileSystemEventHandler):
    def __init__(self, store: MemoryStore) -> None:
        self._store = store
        self._observer: BaseObserver | None = None

    def start(self) -> None:
        observer = Observer()
        observer.schedule(self, str(self._store.vault), recursive=True)
        observer.start()
        self._observer = observer

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None

    # -- watchdog callbacks (they run on the observer's own thread) ----------------

    def on_created(self, event: FileSystemEvent) -> None:
        self._changed(event)

    def on_modified(self, event: FileSystemEvent) -> None:
        self._changed(event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._gone(str(event.src_path))

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self._gone(str(event.src_path))
        self._reindex(str(event.dest_path))

    # -- the work ----------------------------------------------------------------

    def _changed(self, event: FileSystemEvent) -> None:
        if not event.is_directory:
            self._reindex(str(event.src_path))

    def _relative(self, raw: str) -> str | None:
        """The note's path inside the vault, or None if it is not a note we index."""
        try:
            relative = Path(raw).resolve().relative_to(self._store.vault.resolve())
        except ValueError:
            return None
        parts = relative.parts
        if relative.suffix.lower() != ".md":
            return None
        if any(p.startswith(".") for p in parts):
            return None
        if parts[0].lower() == "inbox" and len(parts) > 1:
            return None
        return relative.as_posix()

    def _reindex(self, raw: str) -> None:
        relative = self._relative(raw)
        if relative is None:
            return
        try:
            path = Path(raw)
            if path.exists():
                self._store.reindex_note(path)
            else:
                self._store.remove_note(relative)
        except Exception:  # a half-written file must not kill the observer thread
            logger.exception("could not re-index %s", raw)

    def _gone(self, raw: str) -> None:
        relative = self._relative(raw)
        if relative is None:
            return
        try:
            self._store.remove_note(relative)
        except Exception:
            logger.exception("could not forget %s", raw)
