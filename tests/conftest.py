import pytest

from halo.core.contracts import HaloEvent


class FakeContext:
    """A RunContext that just collects what a skill emits."""

    def __init__(self, run_id: str = "run-test") -> None:
        self.run_id = run_id
        self.events: list[HaloEvent] = []

    def emit(self, event: HaloEvent) -> None:
        self.events.append(event)


@pytest.fixture
def ctx() -> FakeContext:
    return FakeContext()
