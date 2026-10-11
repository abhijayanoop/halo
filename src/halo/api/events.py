"""In-process publish/subscribe bus for HaloEvents.

Components talk only through events: the executor and skills publish, while the
WebSocket, the CLI and the flight recorder subscribe. Publishing never blocks.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from halo.core.contracts import HaloEvent


class EventBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[HaloEvent]] = set()

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    def publish(self, event: HaloEvent) -> None:
        for queue in self._subscribers:
            queue.put_nowait(event)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[HaloEvent]]:
        """Yield a queue that receives every event published while inside the
        block. Events from before subscribing are not replayed."""
        queue: asyncio.Queue[HaloEvent] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)
