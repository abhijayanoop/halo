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


class FakeTransport:
    """A scripted model transport. Each queued item is either a
    TransportResponse to return or an exception to raise."""

    def __init__(self, *script) -> None:
        self.script = list(script)
        self.calls: list[dict] = []

    async def chat(self, *, model_id, messages, json_schema=None, tools=None):
        self.calls.append(
            {
                "model_id": model_id,
                "messages": [dict(m) for m in messages],
                "json_schema": json_schema,
                "tools": tools,
            }
        )
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def reply(content, prompt_tokens=100, completion_tokens=20, tool_calls=None):
    from halo.models.transport import TransportResponse

    return TransportResponse(
        content=content,
        tool_calls=tool_calls or [],
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )


@pytest.fixture
def make_client():
    """Build a ModelClient over a FakeTransport with a known price table."""
    from decimal import Decimal

    from halo.config import HaloConfig, ModelSpec
    from halo.models.client import ModelClient

    def build(*script, local_texts=None, emit=None):
        spec = lambda name: ModelSpec(
            id=f"{name}-id",
            usd_per_m_input=Decimal("0.10"),
            usd_per_m_output=Decimal("0.40"),
        )
        config = HaloConfig(
            models={t: spec(t) for t in ("nano", "super", "ultra", "omni")},
            usd_to_inr=Decimal(80),
        )
        transport = FakeTransport(*script)
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        client = ModelClient(
            config,
            transport,
            emit=emit,
            local_texts=local_texts,
            sleep=fake_sleep,
        )
        return client, transport, sleeps

    return build
