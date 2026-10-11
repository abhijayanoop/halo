import io
import json

import pytest
from conftest import reply
from rich.console import Console

from halo.cli import grant_from_choice, main, render_event, run_request
from halo.core.contracts import ApprovalGrant
from halo.core.events import make_event
from halo.models.transport import TransientModelError


def _intent(app: str) -> str:
    return json.dumps({"skill": "app.open", "args": {"app": app}, "confidence": 0.95})


def _console() -> tuple[Console, io.StringIO]:
    buffer = io.StringIO()
    return Console(
        file=buffer, width=100, force_terminal=False, color_system=None
    ), buffer


async def _never_ask(_request) -> ApprovalGrant:
    raise AssertionError("should not have been asked")


def test_render_event_shows_the_title_for_each_kind_of_event() -> None:
    for type_, title in [
        ("run.started", "open vscode"),
        ("step.started", "Planning"),
        ("tool.result", "Opened vscode"),
        ("approval.requested", "Can I run app.open?"),
        ("run.finished", "Done"),
        ("run.failed", "That didn't work"),
    ]:
        assert title in render_event(make_event("r", type_, title))  # type: ignore[arg-type]


def test_render_event_shows_rupees_for_cost_events() -> None:
    event = make_event(
        "r", "cost.updated", "Nano call", payload={"cost_inr": "0.024", "model": "nano"}
    )
    assert "₹0.024" in render_event(event)
    assert "nano" in render_event(event)


@pytest.mark.parametrize(
    ("choice", "grant"),
    [("y", "allow_once"), ("", "allow_once"), ("n", "deny"), ("a", "always_for_task")],
)
def test_grant_from_choice(choice: str, grant: str) -> None:
    assert grant_from_choice(choice) == grant


def test_grant_from_choice_defaults_to_deny_on_junk() -> None:
    assert grant_from_choice("whatever") == "deny"


async def test_a_run_prints_its_events_and_exits_zero(halo_cm_factory) -> None:
    console, out = _console()
    code = await run_request(
        "open vscode",
        halo_cm=halo_cm_factory(reply(_intent("vscode"))),
        console=console,
        ask=_never_ask,
    )
    text = out.getvalue()
    assert code == 0
    assert text.index("open vscode") < text.index("Planning") < text.index("Done")
    assert len(halo_cm_factory.spawned) == 1


async def test_a_paused_run_asks_and_continues_on_allow(halo_cm_factory) -> None:
    console, out = _console()
    asked = []

    async def ask(request) -> ApprovalGrant:
        asked.append(request)
        return "allow_once"

    code = await run_request(
        "open Spotify",
        halo_cm=halo_cm_factory(reply(_intent("Spotify"))),
        console=console,
        ask=ask,
    )
    assert [r.action for r in asked] == ["app.open"]
    assert "Finished" in out.getvalue()
    assert (
        code == 1
    )  # Spotify is not launchable yet, so the run ends in error, honestly


async def test_deny_exits_nonzero_without_running_the_tool(halo_cm_factory) -> None:
    console, _ = _console()

    async def ask(_request) -> ApprovalGrant:
        return "deny"

    code = await run_request(
        "open Spotify",
        halo_cm=halo_cm_factory(reply(_intent("Spotify"))),
        console=console,
        ask=ask,
    )
    assert code == 1
    assert halo_cm_factory.spawned == []


async def test_a_model_outage_prints_the_failure_and_exits_nonzero(
    halo_cm_factory,
) -> None:
    console, out = _console()
    code = await run_request(
        "open vscode",
        halo_cm=halo_cm_factory(*[TransientModelError("503")] * 8),
        console=console,
        ask=_never_ask,
    )
    assert code == 1
    assert "That didn't work" in out.getvalue()


def test_main_without_an_api_key_explains_what_to_do(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
    config = tmp_path / "empty.toml"
    config.write_text("")
    monkeypatch.setenv("HALO_CONFIG", str(config))
    assert main(["open vscode"]) == 2
    assert "NEBIUS_API_KEY" in capsys.readouterr().out


def test_main_needs_a_request(capsys) -> None:
    assert main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()
