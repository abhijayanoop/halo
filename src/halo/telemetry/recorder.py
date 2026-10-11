"""The flight recorder: every HaloEvent appended to a per-day JSONL file."""

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from halo.api.events import EventBus
from halo.core.contracts import HaloEvent

logger = logging.getLogger(__name__)


def default_runs_dir() -> Path:
    return Path.home() / ".halo" / "runs"


def read_events(path: Path) -> list[HaloEvent]:
    """Parse a recorder file back into events; any invalid line raises."""
    with path.open(encoding="utf-8") as f:
        return [HaloEvent.model_validate_json(line) for line in f if line.strip()]


class FlightRecorder:
    def __init__(self, runs_dir: Path | None = None) -> None:
        self._runs_dir = runs_dir if runs_dir is not None else default_runs_dir()
        self._lock = asyncio.Lock()

    def _path_for(self, event: HaloEvent) -> Path:
        return self._runs_dir / f"{event.ts.astimezone().date().isoformat()}.jsonl"

    def _append(self, path: Path, line: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(line + "\n")

    async def record(self, event: HaloEvent) -> None:
        line = event.model_dump_json()
        async with self._lock:
            await asyncio.to_thread(self._append, self._path_for(event), line)

    @asynccontextmanager
    async def attached(self, bus: EventBus) -> AsyncIterator[None]:
        """Record everything published on `bus` while inside the block, and
        finish writing queued events before leaving it."""
        async with bus.subscribe() as queue:

            async def consume() -> None:
                while True:
                    event = await queue.get()
                    try:
                        await self.record(event)
                    except OSError:
                        logger.exception("could not record event %s", event.id)
                    finally:
                        queue.task_done()

            task = asyncio.create_task(consume())
            try:
                yield
                await queue.join()
            finally:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
