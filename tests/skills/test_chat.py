import pytest
from conftest import FakeContext, reply

from halo.core.context import HaloContext
from halo.skills.chat import skill as chat


def _ctx(client) -> HaloContext:
    return HaloContext(run_id="run1", emit=lambda event: None, model=client)


async def test_replies_with_the_models_text(make_client) -> None:
    client, transport, _ = make_client(reply("Hi! I'm Halo."))
    result = await chat.run(_ctx(client), {"message": "hello"})
    assert result == {"reply": "Hi! I'm Halo."}
    assert [c["model_id"] for c in transport.calls] == ["nano-id"]
    assert transport.calls[0]["messages"][-1] == {"role": "user", "content": "hello"}


async def test_cost_is_attributed_to_the_run(make_client) -> None:
    events = []
    client, _, _ = make_client(reply("hi"), emit=events.append)
    await chat.run(_ctx(client), {"message": "hello"})
    assert [e.run_id for e in events] == ["run1"]


@pytest.mark.parametrize(
    "args", [{}, {"message": ""}, {"message": "  "}, {"message": 3}]
)
async def test_missing_or_blank_message_raises(make_client, args) -> None:
    client, transport, _ = make_client()
    with pytest.raises(ValueError, match="message"):
        await chat.run(_ctx(client), args)
    assert transport.calls == []


async def test_a_context_without_a_model_is_rejected() -> None:
    with pytest.raises(TypeError, match="model"):
        await chat.run(FakeContext(), {"message": "hello"})


def test_halo_context_emits_through_its_callback(make_client) -> None:
    from halo.core.events import make_event

    client, _, _ = make_client()
    seen = []
    ctx = HaloContext(run_id="r", emit=seen.append, model=client)
    event = make_event("r", "mood", "x")
    ctx.emit(event)
    assert seen == [event]
