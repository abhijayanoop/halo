"""The context a skill runs in: the run id, an event sink, and the model client."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from halo.core.contracts import HaloEvent
from halo.memory.store import MemoryStore
from halo.models.client import ModelClient

if TYPE_CHECKING:
    from halo.coding.session import CodeDeps


class HaloContext:
    """Satisfies the frozen `RunContext` protocol, plus the model client for
    skills that need one. Skills reach models only through `model`."""

    def __init__(
        self,
        run_id: str,
        emit: Callable[[HaloEvent], None],
        model: ModelClient,
        *,
        approved: bool = False,
        memory: MemoryStore | None = None,
        code: "CodeDeps | None" = None,
    ) -> None:
        self.run_id = run_id
        self._sink = emit
        self.model = model
        # Set by the executor once the gate has let this step through; a skill
        # may rely on it, and nothing a model returns can change it.
        self.approved = approved
        # The vault, for the memory skills. None when memory is not set up.
        self.memory = memory
        # The coding worker and its cards, for code.task. None when not set up.
        self.code = code

    def emit(self, event: HaloEvent) -> None:
        self._sink(event)
