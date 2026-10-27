"""Status lines: Nano writes them, a template covers every failure."""

import asyncio
import time
from types import SimpleNamespace

import pytest

from halo.character.lines import StatusLines, template_line, valid_line
from halo.core.contracts import HaloEvent
from halo.core.events import make_event
from halo.models.client import ModelUnavailableError


def ev(type_: str, title: str, payload: dict | None = None) -> HaloEvent:
    return make_event("run-1", type_, title, payload=payload)  # type: ignore[arg-type]


class FakeClient:
    def __init__(
        self, text: str | Exception = "Comparing hotels", delay: float = 0
    ) -> None:
        self.text = text
        self.delay = delay
        self.calls: list[dict] = []

    async def call(self, tier, messages, *, run_id=None, **kwargs):
        self.calls.append(
            {"tier": tier, "messages": messages, "run_id": run_id, **kwargs}
        )
        if self.delay:
            await asyncio.sleep(self.delay)
        if isinstance(self.text, Exception):
            raise self.text
        return SimpleNamespace(text=self.text)


# --- validation --------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "Comparing 14 hotels in Anjuna",
        "Ready",
        "Opening Notepad",
        "Can I run npm test?",
    ],
)
def test_good_lines_are_accepted(line: str) -> None:
    assert valid_line(line) is True


@pytest.mark.parametrize(
    "line",
    [
        "",
        "   ",
        "one two three four five six seven eight",  # 8 words
        "Done! 🎉",  # emoji
        "Woo hooray!",  # exclamation mark
        "Two\nlines",
        "x" * 90,
    ],
)
def test_bad_lines_are_rejected(line: str) -> None:
    assert valid_line(line) is False


# --- templates ---------------------------------------------------------------


def test_templates_are_specific_and_short() -> None:
    assert (
        template_line(ev("approval.requested", "Can I run app.open?"))
        == "Can I run app.open?"
    )
    assert template_line(ev("policy.blocked", "x")) == "Blocked something suspicious"
    assert template_line(ev("run.finished", "Done", {"status": "ok"})) == "All done"
    assert (
        template_line(ev("run.finished", "Finished (denied)", {"status": "denied"}))
        == "Stopped, as you asked"
    )
    assert template_line(ev("run.failed", "x")) == "That didn't work"
    assert template_line(
        ev("step.started", "Comparing hotels in Anjuna today please now and later")
    ) == ("Comparing hotels in Anjuna today please now")


def test_every_template_passes_the_same_rules_as_a_model_line() -> None:
    for type_ in (
        "run.started",
        "run.finished",
        "run.failed",
        "step.started",
        "step.finished",
        "tool.called",
        "tool.result",
        "approval.requested",
        "approval.resolved",
        "memory.saved",
        "policy.blocked",
        "voice.listening",
        "agent.spawned",
    ):
        line = template_line(
            ev(type_, "A fairly long title that goes past the seven word limit easily")
        )
        assert valid_line(line), (type_, line)


# --- the model path ----------------------------------------------------------


async def test_a_good_model_line_is_used() -> None:
    client = FakeClient("Comparing 14 hotels")
    lines = StatusLines(client)  # type: ignore[arg-type]
    assert (
        await lines.line(ev("step.started", "Planning"), skill="trip.plan")
        == "Comparing 14 hotels"
    )
    assert client.calls[0]["tier"] == "nano"
    assert client.calls[0]["run_id"] == "run-1"


async def test_quotes_and_a_trailing_full_stop_are_trimmed() -> None:
    lines = StatusLines(FakeClient('"Opening Notepad."'))  # type: ignore[arg-type]
    assert await lines.line(ev("tool.called", "Opening Notepad")) == "Opening Notepad"


@pytest.mark.parametrize(
    "bad", ["", "This is far too long for a status line, honestly", "Yay!", "Done 🎉"]
)
async def test_an_invalid_model_line_falls_back_to_the_template(bad: str) -> None:
    lines = StatusLines(FakeClient(bad))  # type: ignore[arg-type]
    event = ev("run.failed", "boom")
    assert await lines.line(event) == template_line(event)


async def test_a_slow_model_never_holds_up_the_line() -> None:
    lines = StatusLines(FakeClient(delay=5), timeout_s=0.05)  # type: ignore[arg-type]
    event = ev("step.started", "Planning")

    started = time.perf_counter()
    result = await lines.line(event)

    assert result == template_line(event)
    assert time.perf_counter() - started < 1.0


async def test_a_model_error_falls_back_to_the_template() -> None:
    lines = StatusLines(FakeClient(ModelUnavailableError("down")))  # type: ignore[arg-type]
    event = ev("step.started", "Planning")
    assert await lines.line(event) == template_line(event)


# --- cache -------------------------------------------------------------------


async def test_the_same_skill_event_and_title_is_asked_only_once() -> None:
    client = FakeClient("Comparing hotels")
    lines = StatusLines(client)  # type: ignore[arg-type]
    event = ev("step.started", "Planning")

    first = await lines.line(event, skill="trip.plan")
    second = await lines.line(ev("step.started", "Planning"), skill="trip.plan")

    assert first == second
    assert len(client.calls) == 1


async def test_a_different_title_or_skill_is_a_different_line() -> None:
    client = FakeClient("Working on it")
    lines = StatusLines(client)  # type: ignore[arg-type]
    await lines.line(ev("step.started", "Planning"), skill="trip.plan")
    await lines.line(ev("step.started", "Booking"), skill="trip.plan")
    await lines.line(ev("step.started", "Planning"), skill="expense.log")
    assert len(client.calls) == 3


async def test_a_failed_attempt_is_not_cached_so_a_later_one_can_succeed() -> None:
    client = FakeClient("")
    lines = StatusLines(client)  # type: ignore[arg-type]
    event = ev("step.started", "Planning")
    await lines.line(event)

    client.text = "Planning your trip"
    assert await lines.line(event) == "Planning your trip"
    assert len(client.calls) == 2


# --- voice -------------------------------------------------------------------


@pytest.mark.parametrize(
    "type_", ["approval.requested", "run.failed", "policy.blocked"]
)
async def test_serious_moments_are_asked_for_in_a_plain_voice(type_: str) -> None:
    client = FakeClient("Blocked a hidden instruction")
    await StatusLines(client).line(ev(type_, "x"))  # type: ignore[arg-type]
    system = client.calls[0]["messages"][0]["content"].lower()
    assert "plain and serious" in system
    assert "no exclamation" in system


async def test_happy_moments_may_be_warm() -> None:
    client = FakeClient("All sorted")
    await StatusLines(client).line(ev("run.finished", "Done", {"status": "ok"}))  # type: ignore[arg-type]
    assert "warm" in client.calls[0]["messages"][0]["content"].lower()
