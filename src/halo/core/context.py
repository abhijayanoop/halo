"""The context a skill runs in: the run id, an event sink, and the model client."""

from collections.abc import Callable

from halo.core.contracts import HaloEvent
from halo.models.client import ModelClient


class HaloContext:
    """Satisfies the frozen `RunContext` protocol, plus the model client for
    skills that need one. Skills reach models only through `model`."""

    def __init__(
        self,
        run_id: str,
        emit: Callable[[HaloEvent], None],
        model: ModelClient,
    ) -> None:
        self.run_id = run_id
        self._sink = emit
        self.model = model

    def emit(self, event: HaloEvent) -> None:
        self._sink(event)
