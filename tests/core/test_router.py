import pytest
from conftest import reply

from halo.core.contracts import HaloEvent, Intent
from halo.core.router import route
from halo.models.client import ModelUnavailableError
from halo.models.transport import TransientModelError


def _intent(skill: str, confidence: float = 0.95, args: str = "{}") -> str:
    return f'{{"skill": "{skill}", "args": {args}, "confidence": {confidence}}}'


async def test_routes_a_request_to_an_intent_using_nano(make_client) -> None:
    client, transport, _ = make_client(
        reply(_intent("app.open", args='{"app": "vs code"}'))
    )
    intent = await route(client, "open VS Code")
    assert intent == Intent(skill="app.open", args={"app": "vs code"}, confidence=0.95)
    assert [c["model_id"] for c in transport.calls] == ["nano-id"]


async def test_low_confidence_nano_answer_escalates_to_super(make_client) -> None:
    client, transport, _ = make_client(
        reply(_intent("chat", 0.4)), reply(_intent("memory.recall", 0.9))
    )
    intent = await route(client, "open the Goa trip note")
    assert intent.skill == "memory.recall"
    assert [c["model_id"] for c in transport.calls] == ["nano-id", "super-id"]


async def test_prompt_lists_every_skill_and_ends_with_the_request(make_client) -> None:
    from typing import get_args

    from halo.core.contracts import SkillName

    client, transport, _ = make_client(reply(_intent("chat")))
    await route(client, "hello there")
    messages = transport.calls[0]["messages"]
    system = messages[0]["content"]
    for skill in get_args(SkillName):
        assert skill in system
    assert messages[0]["role"] == "system"
    assert messages[-1] == {"role": "user", "content": "hello there"}


async def test_context_goes_under_a_sources_heading(make_client) -> None:
    client, transport, _ = make_client(reply(_intent("chat")))
    await route(client, "hi", context="- Picked pywebview [src:: you]")
    system = transport.calls[0]["messages"][0]["content"]
    assert "What you know, with sources" in system
    assert "Picked pywebview" in system


async def test_no_context_means_no_sources_heading(make_client) -> None:
    client, transport, _ = make_client(reply(_intent("chat")))
    await route(client, "hi")
    assert "What you know" not in transport.calls[0]["messages"][0]["content"]


@pytest.mark.parametrize(
    "phrase",
    [
        "let's get to work",
        "Let's get to work!",
        "LETS GET TO WORK",
        "lets get started.",
        "  let’s get started  ",
    ],
)
async def test_work_start_phrases_skip_the_model(make_client, phrase: str) -> None:
    client, transport, _ = make_client()
    intent = await route(client, phrase)
    assert intent == Intent(skill="work.start", args={}, confidence=1.0)
    assert transport.calls == []


async def test_phrase_inside_a_longer_request_is_not_a_shortcut(make_client) -> None:
    client, transport, _ = make_client(reply(_intent("chat")))
    intent = await route(client, "let's get to work on the webhook limiter")
    assert intent.skill == "chat"
    assert len(transport.calls) == 1


async def test_cost_events_carry_the_run_id(make_client) -> None:
    events: list[HaloEvent] = []
    client, _, _ = make_client(reply(_intent("chat")), emit=events.append)
    await route(client, "hi", run_id="run9")
    assert [(e.type, e.run_id) for e in events] == [("cost.updated", "run9")]


async def test_total_outage_raises(make_client) -> None:
    client, _, _ = make_client(*[TransientModelError("503")] * 8)
    with pytest.raises(ModelUnavailableError):
        await route(client, "hi")
