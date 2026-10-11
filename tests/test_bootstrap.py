import json
from pathlib import Path

import pytest
from conftest import reply

from halo.bootstrap import open_halo
from halo.config import HaloConfig
from halo.models.client import ConfigError
from halo.telemetry.recorder import read_events


def _intent(skill: str, app: str) -> str:
    return json.dumps({"skill": skill, "args": {"app": app}, "confidence": 0.95})


async def test_a_run_reaches_bus_subscribers_and_the_flight_recorder(
    halo_cm_factory, tmp_path: Path
) -> None:
    home = tmp_path / "home"
    async with (
        halo_cm_factory(reply(_intent("app.open", "vscode")), home=home)() as halo,
        halo.bus.subscribe() as queue,
    ):
        outcome = await halo.runner.run("open vscode", run_id="r1")
        seen = []
        while not queue.empty():
            seen.append(queue.get_nowait())

    assert outcome.state == "finished"
    assert "run.finished" in [e.type for e in seen]
    (path,) = (home / "runs").glob("*.jsonl")
    recorded = read_events(path)
    assert [e.id for e in recorded] == [e.id for e in seen]
    # the model client's cost events travel the same bus, so the wiring is complete
    assert "cost.updated" in [e.type for e in recorded]


async def test_halo_home_is_created_with_a_checkpoint_database(
    halo_cm_factory, tmp_path: Path
) -> None:
    home = tmp_path / "fresh" / ".halo"
    async with halo_cm_factory(
        reply(_intent("app.open", "vscode")), home=home
    )() as halo:
        await halo.runner.run("open vscode")
    assert (home / "checkpoints.db").is_file()
    assert (home / "runs").is_dir()


async def test_opening_halo_for_real_without_an_api_key_is_a_config_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)  # no .env here
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    with pytest.raises(ConfigError, match="NEBIUS_API_KEY"):
        async with open_halo(HaloConfig(), home=tmp_path / "h"):
            pass
