from contextlib import asynccontextmanager
from pathlib import Path

import pytest

from halo.core.contracts import HaloEvent


@pytest.fixture(autouse=True)
def _no_ambient_halo_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must not depend on the developer's own HALO_* settings."""
    monkeypatch.delenv("HALO_PROFILE", raising=False)
    monkeypatch.delenv("HALO_CONFIG", raising=False)


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


VSCODE_CONFIG = """
[apps.vscode]
aliases = ["vs code", "vscode"]

[apps.vscode.command]
win32 = ["code"]
darwin = ["open", "-a", "Visual Studio Code"]
linux = ["code"]
"""


@pytest.fixture
def open_runner(tmp_path: Path, make_client, monkeypatch: pytest.MonkeyPatch):
    """Open a HaloRunner over a fake model and a real SQLite checkpointer.

    Returns an async context manager yielding (runner, events, transport,
    spawned). `spawned` records app launches; nothing is really started.
    """
    from halo.core.graph import GraphDeps, build_graph, open_checkpointer
    from halo.core.runner import HaloRunner
    from halo.skills.registry import SkillRegistry, default_skills_dir

    config = tmp_path / "config.toml"
    config.write_text(VSCODE_CONFIG)
    monkeypatch.setenv("HALO_CONFIG", str(config))

    @asynccontextmanager
    async def opener(*script, db: Path | None = None, registry=None):
        events: list = []
        client, transport, _ = make_client(*script, emit=events.append)
        registry = registry or SkillRegistry.load(default_skills_dir())
        spawned: list[list[str]] = []

        async def fake_spawn(argv: list[str]) -> None:
            spawned.append(argv)

        monkeypatch.setattr(registry.get("app.open").module, "_spawn", fake_spawn)
        async with open_checkpointer(db or tmp_path / "checkpoints.db") as checkpointer:
            graph = build_graph(
                GraphDeps(client, registry, events.append), checkpointer
            )
            yield HaloRunner(graph, events.append), events, transport, spawned

    return opener


@pytest.fixture
def halo_cm_factory(tmp_path: Path, make_client, monkeypatch: pytest.MonkeyPatch):
    """Returns `factory(*script, home=None)` giving a zero-arg callable that opens
    a fully wired Halo (bus, recorder, checkpointer, runner) over a fake model.
    App launches are recorded in `factory.spawned`, never executed."""
    from halo.bootstrap import open_halo
    from halo.config import load_config
    from halo.skills.registry import SkillRegistry, default_skills_dir

    config_path = tmp_path / "config.toml"
    config_path.write_text(VSCODE_CONFIG)
    monkeypatch.setenv("HALO_CONFIG", str(config_path))
    spawned: list[list[str]] = []

    def factory(*script, home: Path | None = None):
        registry = SkillRegistry.load(default_skills_dir())

        async def fake_spawn(argv: list[str]) -> None:
            spawned.append(argv)

        monkeypatch.setattr(registry.get("app.open").module, "_spawn", fake_spawn)

        def client_factory(emit):
            return make_client(*script, emit=emit)[0]

        return lambda: open_halo(
            load_config(),
            home=home or tmp_path / "halo-home",
            client_factory=client_factory,
            registry=registry,
        )

    factory.spawned = spawned  # type: ignore[attr-defined]
    return factory
