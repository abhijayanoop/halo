import logging

import pytest
from conftest import reply

from halo.core.contracts import HaloEvent, Intent
from halo.models.cascade import cascade_call
from halo.models.client import ModelUnavailableError, ModelValidationError
from halo.models.transport import TransientModelError

MSGS = [{"role": "user", "content": "open vs code"}]


def _intent(confidence: float, skill: str = "app.open") -> str:
    return f'{{"skill": "{skill}", "args": {{}}, "confidence": {confidence}}}'


async def test_confident_nano_answer_is_final(make_client) -> None:
    client, transport, _ = make_client(reply(_intent(0.95)))
    result = await cascade_call(client, MSGS, Intent)
    assert result.tier == "nano"
    assert result.escalations == []
    assert [c["model_id"] for c in transport.calls] == ["nano-id"]


async def test_low_confidence_escalates_to_super(make_client) -> None:
    client, transport, _ = make_client(reply(_intent(0.4, "chat")), reply(_intent(0.9)))
    result = await cascade_call(client, MSGS, Intent)
    assert result.tier == "super"
    assert result.parsed.skill == "app.open"
    assert [c["model_id"] for c in transport.calls] == ["nano-id", "super-id"]
    assert [(e.from_tier, e.reason) for e in result.escalations] == [
        ("nano", "low_confidence")
    ]


async def test_confidence_exactly_at_threshold_does_not_escalate(make_client) -> None:
    client, transport, _ = make_client(reply(_intent(0.7)))
    result = await cascade_call(client, MSGS, Intent)
    assert result.tier == "nano"
    assert len(transport.calls) == 1


async def test_validation_failure_after_retry_escalates(make_client) -> None:
    client, transport, _ = make_client(
        reply("garbage"), reply("garbage"), reply(_intent(0.9))
    )
    result = await cascade_call(client, MSGS, Intent)
    assert result.tier == "super"
    assert [e.reason for e in result.escalations] == ["validation_failed"]
    assert [c["model_id"] for c in transport.calls] == [
        "nano-id",
        "nano-id",
        "super-id",
    ]


async def test_outage_on_nano_escalates_to_super(make_client) -> None:
    client, _, _ = make_client(*[TransientModelError("503")] * 4, reply(_intent(0.9)))
    result = await cascade_call(client, MSGS, Intent)
    assert result.tier == "super"
    assert [e.reason for e in result.escalations] == ["unavailable"]


async def test_low_confidence_from_the_last_tier_is_returned_anyway(
    make_client,
) -> None:
    client, _, _ = make_client(reply(_intent(0.3)), reply(_intent(0.2)))
    result = await cascade_call(client, MSGS, Intent)
    assert result.tier == "super"
    assert result.parsed.confidence == 0.2


async def test_failure_on_every_tier_raises_the_last_error(make_client) -> None:
    client, _, _ = make_client(reply("x"), reply("x"), reply("x"), reply("x"))
    with pytest.raises(ModelValidationError):
        await cascade_call(client, MSGS, Intent)


async def test_outage_on_every_tier_raises_unavailable(make_client) -> None:
    client, _, _ = make_client(*[TransientModelError("503")] * 8)
    with pytest.raises(ModelUnavailableError):
        await cascade_call(client, MSGS, Intent)


async def test_every_escalation_is_logged(make_client, caplog) -> None:
    client, _, _ = make_client(reply(_intent(0.4)), reply(_intent(0.9)))
    with caplog.at_level(logging.INFO, logger="halo.models.cascade"):
        await cascade_call(client, MSGS, Intent)
    assert "escalat" in caplog.text
    assert "nano" in caplog.text
    assert "low_confidence" in caplog.text


async def test_escalated_call_is_marked_on_its_cost_event(make_client) -> None:
    events: list[HaloEvent] = []
    client, _, _ = make_client(
        reply(_intent(0.4)), reply(_intent(0.9)), emit=events.append
    )
    await cascade_call(client, MSGS, Intent, run_id="r1")
    assert [e.payload["model"] for e in events] == ["nano", "super"]
    assert "escalated_from" not in events[0].payload
    assert events[1].payload["escalated_from"] == "nano"
    assert events[1].payload["escalation_reason"] == "low_confidence"


async def test_custom_tiers_and_threshold(make_client) -> None:
    client, transport, _ = make_client(reply(_intent(0.85)), reply(_intent(0.99)))
    result = await cascade_call(
        client, MSGS, Intent, tiers=("super", "ultra"), min_confidence=0.9
    )
    assert result.tier == "ultra"
    assert [c["model_id"] for c in transport.calls] == ["super-id", "ultra-id"]
