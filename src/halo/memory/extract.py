"""After a run, Nano may propose facts worth remembering.

Only the user's own words go to the model, never a page, a file or a tool's
output, so nothing untrusted can plant a proposal. Whatever the model says about
source or trust, a proposal is marked as an agent's inference with medium trust.
It waits in the inbox until the user approves it: a proposal is never a memory.

It costs a Nano call per finished run, so it is opt-in (HALO_MEMORY_EXTRACT=1).
"""

import asyncio
import logging
import os
from collections.abc import Mapping
from contextlib import AsyncExitStack
from types import TracebackType
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field

from halo.api.events import EventBus
from halo.core.contracts import HaloEvent, MemoryCandidate
from halo.memory.events import proposed_event
from halo.memory.store import MemoryStore
from halo.models.client import (
    ConfigError,
    ModelClient,
    ModelUnavailableError,
    ModelValidationError,
    PrivacyViolationError,
)
from halo.models.transport import ModelRequestError

logger = logging.getLogger(__name__)

MAX_CANDIDATES = 3
MAX_FACT_CHARS = 200
_NO_MINING = ("memory.",)  # remembering, recalling or forgetting is not new material

_SYSTEM = (
    "You read what a user asked their desktop assistant and list at most three durable "
    "facts about the user worth remembering: preferences, decisions, names, paths, "
    "how they like to work. Skip anything one-off, and skip secrets, passwords, keys "
    "and money. Each fact is one short sentence in the third person. subject is the "
    'project or topic it belongs to (for example "halo"), or "" if general. Reply with '
    'JSON only: {"candidates": [{"fact": ..., "subject": ...}]}. Use [] if nothing '
    "is worth keeping."
)


class _Raw(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fact: str = ""
    subject: str = ""


class _Extracted(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidates: list[_Raw] = Field(default_factory=list)


async def extract_candidates(
    client: ModelClient, request: str, run_id: str
) -> list[MemoryCandidate]:
    """Facts worth remembering from the user's request, or [] (also on any model failure)."""
    if not request.strip():
        return []
    try:
        result = await client.call(
            "nano",
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": request},
            ],
            schema=_Extracted,
            run_id=run_id,
        )
    except (
        ModelUnavailableError,
        ModelValidationError,
        ModelRequestError,
        PrivacyViolationError,
        ConfigError,
    ):
        logger.info("memory extraction skipped for run %s", run_id)
        return []
    parsed = result.parsed
    if parsed is None:
        return []
    found: list[MemoryCandidate] = []
    for raw in parsed.candidates:
        fact = " ".join(raw.fact.split())
        if not fact or len(fact) > MAX_FACT_CHARS:
            continue
        found.append(
            MemoryCandidate(
                fact=fact, subject=raw.subject.strip(), source="agent", trust="medium"
            )
        )
        if len(found) == MAX_CANDIDATES:
            break
    return found


class MemoryExtractor:
    """Listens to the bus; when a run finishes well, proposes memories from the
    user's request and announces each with a `memory.proposed` event."""

    def __init__(self, bus: EventBus, client: ModelClient, store: MemoryStore) -> None:
        self._bus = bus
        self._client = client
        self._store = store
        self._stack = AsyncExitStack()
        self._tasks: set[asyncio.Task[Any]] = set()
        self._runs: dict[str, dict[str, str]] = {}

    async def __aenter__(self) -> Self:
        queue = await self._stack.enter_async_context(self._bus.subscribe())
        self._listener = asyncio.ensure_future(self._listen(queue))
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self._listener.cancel()
        for task in list(self._tasks):
            task.cancel()
        await asyncio.gather(self._listener, *self._tasks, return_exceptions=True)
        await self._stack.aclose()

    async def _listen(self, queue: "asyncio.Queue[HaloEvent]") -> None:
        while True:
            self._see(await queue.get())

    def _see(self, event: HaloEvent) -> None:
        run = self._runs.setdefault(event.run_id, {})
        match event.type:
            case "run.started":
                self._runs[event.run_id] = {
                    "request": str(event.payload.get("request", ""))
                }
            case "step.finished" if event.payload.get("stage") == "route":
                run["skill"] = str(event.payload.get("skill", ""))
            case "run.failed":
                self._runs.pop(event.run_id, None)
            case "run.finished":
                info = self._runs.pop(event.run_id, {})
                if (
                    event.payload.get("status") == "ok"
                    and info.get("request")
                    and not info.get("skill", "").startswith(_NO_MINING)
                ):
                    task = asyncio.ensure_future(
                        self._mine(event.run_id, info["request"])
                    )
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)

    async def _mine(self, run_id: str, request: str) -> None:
        for candidate in await extract_candidates(self._client, request, run_id):
            proposal_id = await asyncio.to_thread(self._store.propose, candidate)
            if proposal_id:
                self._bus.publish(proposed_event(proposal_id, candidate))


def extractor_for(
    bus: EventBus,
    client: ModelClient,
    store: MemoryStore,
    env: Mapping[str, str] | None = None,
) -> MemoryExtractor | None:
    """The extractor when HALO_MEMORY_EXTRACT=1, otherwise None."""
    env = os.environ if env is None else env
    if env.get("HALO_MEMORY_EXTRACT") == "1":
        return MemoryExtractor(bus, client, store)
    return None
