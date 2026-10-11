"""Assembles a running Halo: bus, model client, skills, checkpointer, runner
and the flight recorder, wired together. The CLI and the server both open Halo
through here so they behave identically."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from halo.api.events import EventBus
from halo.character.director import MoodDirector
from halo.config import HaloConfig
from halo.core.contracts import HaloEvent
from halo.core.graph import GraphDeps, build_graph, open_checkpointer
from halo.core.runner import HaloRunner
from halo.models.client import ModelClient, build_client
from halo.skills.registry import SkillRegistry, default_skills_dir
from halo.telemetry.recorder import FlightRecorder

ClientFactory = Callable[[Callable[[HaloEvent], None]], ModelClient]


def default_home() -> Path:
    return Path.home() / ".halo"


@dataclass
class Halo:
    bus: EventBus
    runner: HaloRunner
    registry: SkillRegistry


@asynccontextmanager
async def open_halo(
    config: HaloConfig,
    *,
    home: Path | None = None,
    client_factory: ClientFactory | None = None,
    registry: SkillRegistry | None = None,
) -> AsyncIterator[Halo]:
    """Open Halo with state under `home` (default ~/.halo). `client_factory`
    receives the bus's publish function so model cost events join the stream;
    the default builds the real Token Factory client and raises ConfigError if
    it is not set up."""
    home = home or default_home()
    bus = EventBus()
    make_client = client_factory or (lambda emit: build_client(config, emit=emit))
    client = make_client(bus.publish)
    registry = registry or SkillRegistry.load(default_skills_dir())

    recorder = FlightRecorder(home / "runs")
    async with (
        open_checkpointer(home / "checkpoints.db") as checkpointer,
        recorder.attached(bus),
        MoodDirector(bus),
    ):
        graph = build_graph(GraphDeps(client, registry, bus.publish), checkpointer)
        yield Halo(bus, HaloRunner(graph, bus.publish), registry)
