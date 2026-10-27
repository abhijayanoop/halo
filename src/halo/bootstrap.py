"""Assembles a running Halo: bus, model client, skills, checkpointer, runner
and the flight recorder, wired together. The CLI and the server both open Halo
through here so they behave identically."""

import asyncio
import os
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from halo.api.events import EventBus
from halo.character.director import MoodDirector
from halo.character.lines import StatusLines
from halo.config import HaloConfig
from halo.core.contracts import HaloEvent
from halo.core.graph import GraphDeps, build_graph, open_checkpointer
from halo.core.runner import HaloRunner
from halo.memory.extract import extractor_for
from halo.memory.store import MemoryStore
from halo.memory.watch import VaultWatcher
from halo.models.client import ModelClient, build_client
from halo.skills.registry import SkillRegistry, default_skills_dir
from halo.telemetry.recorder import FlightRecorder

ClientFactory = Callable[[Callable[[HaloEvent], None]], ModelClient]


def status_lines_for(
    client: ModelClient, env: Mapping[str, str] | None = None
) -> StatusLines | None:
    """Nano-written status lines cost a model call per mood change, so they are
    opt-in (HALO_STATUS_LINES=1) until reasoning-off latency is measured. The
    template lines always work."""
    env = os.environ if env is None else env
    return StatusLines(client) if env.get("HALO_STATUS_LINES") == "1" else None


def default_home() -> Path:
    return Path.home() / ".halo"


@dataclass
class Halo:
    bus: EventBus
    runner: HaloRunner
    registry: SkillRegistry
    memory: MemoryStore | None = None


def vault_path(config: HaloConfig, home: Path | None) -> Path:
    """Where the Obsidian vault lives: the configured path, else ~/HaloVault. A
    caller that passes its own `home` (tests, sandboxes) gets a vault inside it,
    so nothing but the real app ever touches the real vault."""
    if config.vault.path is not None:
        return config.vault.path.expanduser()
    return Path.home() / "HaloVault" if home is None else home / "vault"


@asynccontextmanager
async def open_halo(
    config: HaloConfig,
    *,
    home: Path | None = None,
    client_factory: ClientFactory | None = None,
    registry: SkillRegistry | None = None,
    watch: bool = False,
) -> AsyncIterator[Halo]:
    """Open Halo with state under `home` (default ~/.halo). `client_factory`
    receives the bus's publish function so model cost events join the stream;
    the default builds the real Token Factory client and raises ConfigError if
    it is not set up. The vault is created on first use and its `privacy: local`
    notes feed the guard that keeps them out of cloud prompts. With `watch`,
    notes edited elsewhere (Obsidian) are re-indexed as they are saved."""
    explicit_home = home is not None
    home = home or default_home()
    bus = EventBus()
    memory = MemoryStore(
        vault_path(config, home if explicit_home else None), home / "memory.db"
    )
    await asyncio.to_thread(memory.start)
    make_client = client_factory or (
        lambda emit: build_client(config, emit=emit, local_texts=memory.local_texts)
    )
    watcher = VaultWatcher(memory) if watch else None
    try:
        client = make_client(bus.publish)
        registry = registry or SkillRegistry.load(default_skills_dir())

        recorder = FlightRecorder(home / "runs")
        async with (
            open_checkpointer(home / "checkpoints.db") as checkpointer,
            recorder.attached(bus),
            MoodDirector(bus, lines=status_lines_for(client)),
        ):
            graph = build_graph(
                GraphDeps(client, registry, bus.publish, memory=memory), checkpointer
            )
            if watcher is not None:
                watcher.start()
            try:
                # Nano proposing memories after a run is opt-in (HALO_MEMORY_EXTRACT=1).
                async with AsyncExitStack() as stack:
                    extractor = extractor_for(bus, client, memory)
                    if extractor is not None:
                        await stack.enter_async_context(extractor)
                    yield Halo(bus, HaloRunner(graph, bus.publish), registry, memory)
            finally:
                if watcher is not None:
                    watcher.stop()
    finally:
        memory.close()
