"""open_halo wires memory in: the vault, the privacy guard and the file watcher."""

import json
from pathlib import Path

import pytest
from conftest import reply

from halo.bootstrap import open_halo, vault_path
from halo.config import HaloConfig, load_config
from halo.core.contracts import ApprovalDecision


def _intent(skill: str, **args) -> str:
    return json.dumps({"skill": skill, "args": args, "confidence": 0.95})


@pytest.fixture
def config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> HaloConfig:
    path = tmp_path / "config.toml"
    path.write_text("", encoding="utf-8")
    monkeypatch.setenv("HALO_CONFIG", str(path))
    return load_config()


def test_the_vault_defaults_to_halovault_in_the_users_home(config: HaloConfig) -> None:
    assert vault_path(config, None) == Path.home() / "HaloVault"


def test_with_an_explicit_home_the_vault_lives_inside_it(
    config: HaloConfig, tmp_path: Path
) -> None:
    """Tests and sandboxes pass a home and must never touch the real vault."""
    assert vault_path(config, tmp_path) == tmp_path / "vault"


def test_a_configured_vault_path_wins(tmp_path: Path) -> None:
    config = HaloConfig.model_validate({"vault": {"path": str(tmp_path / "mine")}})
    assert vault_path(config, tmp_path / "home") == tmp_path / "mine"


async def test_open_halo_creates_the_vault_and_a_remembered_fact_is_recalled(
    config: HaloConfig, tmp_path: Path, make_client
) -> None:
    script = [
        reply(_intent("memory.remember", fact="I picked pywebview for the HUD window")),
        reply(_intent("memory.recall", query="what did I pick for the HUD window")),
    ]
    client, _, _ = make_client(*script)
    async with open_halo(
        config, home=tmp_path / "home", client_factory=lambda emit: client
    ) as halo:
        assert halo.memory is not None
        assert (tmp_path / "home" / "vault" / "Profile.md").is_file()
        first = await halo.runner.run("remember that I picked pywebview", run_id="b1")
        assert first.state == "finished"
        second = await halo.runner.run(
            "what did I pick for the HUD window?", run_id="b2"
        )
    answer = second.results[0]["result"]["answer"]
    assert "pywebview" in answer


async def test_memory_survives_closing_and_reopening_halo(
    config: HaloConfig, tmp_path: Path, make_client
) -> None:
    home = tmp_path / "home"
    client, _, _ = make_client(
        reply(_intent("memory.remember", fact="I picked pywebview for the HUD window"))
    )
    async with open_halo(config, home=home, client_factory=lambda e: client) as halo:
        await halo.runner.run("remember that I picked pywebview", run_id="r1")

    again, _, _ = make_client(
        reply(_intent("memory.recall", query="what did I pick for the HUD window"))
    )
    async with open_halo(config, home=home, client_factory=lambda e: again) as halo:
        out = await halo.runner.run("what did I pick for the HUD window?", run_id="r2")
    assert "pywebview" in out.results[0]["result"]["answer"]


async def test_the_real_client_is_built_with_the_privacy_guard_fed_by_the_vault(
    config: HaloConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_client
) -> None:
    seen: dict = {}
    fake, _, _ = make_client()

    def fake_build(cfg, *, emit=None, local_texts=None):
        seen["local_texts"] = local_texts
        return fake

    monkeypatch.setattr("halo.bootstrap.build_client", fake_build)
    async with open_halo(config, home=tmp_path / "home") as halo:
        assert halo.memory is not None
        halo.memory.remember("my salary is twelve lakh", note="Finance/pay.md")
        halo.memory.remember("I like green tea")
        texts = seen["local_texts"]()
    assert any("salary is twelve lakh" in t for t in texts)
    assert not any("green tea" in t for t in texts)


async def test_a_prompt_that_copies_a_local_note_is_refused_end_to_end(
    config: HaloConfig, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, make_client
) -> None:
    """The guard is live: text from a privacy: local note in a request never reaches the model."""
    from halo.models.client import ModelClient

    real: dict = {}

    def build(cfg, *, emit=None, local_texts=None):
        client, transport, _ = make_client(
            reply(_intent("chat", message="x")), emit=emit, local_texts=local_texts
        )
        real["transport"] = transport
        assert isinstance(client, ModelClient)
        return client

    monkeypatch.setattr("halo.bootstrap.build_client", build)
    async with open_halo(config, home=tmp_path / "home") as halo:
        assert halo.memory is not None
        halo.memory.remember(
            "my monthly salary is twelve lakh rupees after tax deductions",
            note="Finance/pay.md",
        )
        outcome = await halo.runner.run(
            "my monthly salary is twelve lakh rupees after tax deductions", run_id="g1"
        )
    assert outcome.state == "failed"
    assert real["transport"].calls == []  # nothing was sent


async def test_the_watcher_forgets_a_line_deleted_outside_halo(
    config: HaloConfig, tmp_path: Path, make_client
) -> None:
    import asyncio

    client, _, _ = make_client()
    async with open_halo(
        config, home=tmp_path / "home", client_factory=lambda e: client, watch=True
    ) as halo:
        assert halo.memory is not None
        halo.memory.remember("I picked pywebview for the HUD window")
        assert halo.memory.recall("pywebview")
        (tmp_path / "home" / "vault" / "Profile.md").write_text(
            "# Profile\n", encoding="utf-8"
        )
        for _ in range(100):  # up to 5 s for the file system event to arrive
            if not halo.memory.recall("pywebview"):
                break
            await asyncio.sleep(0.05)
        assert halo.memory.recall("pywebview") == []


async def test_a_forget_through_open_halo_needs_the_card(
    config: HaloConfig, tmp_path: Path, make_client
) -> None:
    client, _, _ = make_client(reply(_intent("memory.forget", query="pywebview")))
    async with open_halo(
        config, home=tmp_path / "home", client_factory=lambda e: client
    ) as halo:
        assert halo.memory is not None
        halo.memory.remember("I picked pywebview for the HUD window")
        paused = await halo.runner.run("forget the pywebview thing", run_id="f1")
        assert paused.state == "paused"
        assert paused.approval is not None
        await halo.runner.resume(
            "f1",
            ApprovalDecision(
                approval_id=paused.approval.approval_id, grant="allow_once"
            ),
        )
        assert halo.memory.recall("pywebview") == []


async def test_extraction_is_wired_in_when_enabled(
    config: HaloConfig,
    tmp_path: Path,
    make_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    monkeypatch.setenv("HALO_MEMORY_EXTRACT", "1")
    facts = json.dumps(
        {"candidates": [{"fact": "Prefers pytest over unittest", "subject": "halo"}]}
    )
    client, _, _ = make_client(
        reply(_intent("chat", message="hi")), reply("hello there"), reply(facts)
    )
    async with open_halo(
        config, home=tmp_path / "home", client_factory=lambda e: client
    ) as halo:
        assert halo.memory is not None
        await halo.runner.run("I always use pytest, never unittest", run_id="x1")
        for _ in range(100):
            if halo.memory.proposals():
                break
            await asyncio.sleep(0.05)
        assert [p.candidate.fact for p in halo.memory.proposals()] == [
            "Prefers pytest over unittest"
        ]


async def test_extraction_is_off_by_default(
    config: HaloConfig,
    tmp_path: Path,
    make_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import asyncio

    monkeypatch.delenv("HALO_MEMORY_EXTRACT", raising=False)
    client, transport, _ = make_client(
        reply(_intent("chat", message="hi")), reply("hello there")
    )
    async with open_halo(
        config, home=tmp_path / "home", client_factory=lambda e: client
    ) as halo:
        assert halo.memory is not None
        await halo.runner.run("I always use pytest, never unittest", run_id="x2")
        await asyncio.sleep(0.2)
        assert halo.memory.proposals() == []
    assert len(transport.calls) == 2  # the router and the chat reply, nothing more
