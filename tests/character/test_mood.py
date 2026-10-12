"""Tests for halo.character.mood (written before the implementation).

API under test
--------------
Mood(StrEnum): asleep, waking, idle, listening, thinking, focused, delegating,
    careful, remembering, asking, guarding, delighted, confused.
MoodEngine(clock=time.monotonic):
    feed(event) -> list[HaloEvent]   zero or more type="mood" events
    tick() -> list[HaloEvent]        time-based transitions, uses the clock
    current -> Mood                  starts as Mood.IDLE

Mood event: type="mood", run_id of the triggering event (for tick(): the run_id
of the last event fed), payload {"mood": <name>, "previous": <name>}, and
title == mood.capitalize() (e.g. "Thinking").

Decisions the architecture table left open (the tests encode these)
-------------------------------------------------------------------
Triggers, using only types that exist in HaloEventType:
  Listening   voice.listening                  released by voice.heard
  Thinking    run.started, step.started        released by run.finished / run.failed
  Focused     tool.called                      released by tool.result
  Careful     tool.called with payload {"untrusted": True}
              (there is no reader event type; the flag is the signal);
              does NOT also count as Focused; released by tool.result
  Delegating  agent.spawned                    released by agent.finished
  Remembering memory.proposed / memory.saved   lasts 2 s, then released by tick()
  Asking      approval.requested               released by approval.resolved
  Guarding    policy.blocked                   held until the next run.started
  Confused    run.failed                       held until the next run.started
  Delighted   run.finished, payload status "ok" (runner.py's success status);
              lasts 2 s, then Idle via tick(). "error"/"denied" never delight.
The engine keeps a set of active conditions and shows the highest-priority one.
Dwell: the initial Idle has no dwell (first change is immediate). Every later
change must be >= 0.7 s after the previous one, else it is deferred to tick().
Asking bypasses the dwell when ENTERED (a permission request must never wait);
leaving Asking respects the dwell.
Asleep: 600 s after the last event fed (not the last mood change), via tick().
Waking: the first event fed while Asleep emits Waking; the mood that event
implies is deferred until the dwell elapses (emitted by tick()).
"""

from itertools import combinations

import pytest

from halo.character.mood import Mood, MoodEngine
from halo.core.contracts import HaloEvent
from halo.core.events import make_event

DWELL_OK = 0.75  # > 0.7 s dwell, exactly representable as a float
TOO_SOON = 0.25


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def ev(type_: str, payload: dict | None = None, run_id: str = "run-1") -> HaloEvent:
    return make_event(run_id, type_, f"{type_} title", payload=payload)  # type: ignore[arg-type]


# Event that triggers each event-driven mood.
TRIGGERS: dict[Mood, tuple[str, dict | None]] = {
    Mood.ASKING: ("approval.requested", None),
    Mood.GUARDING: ("policy.blocked", None),
    Mood.CONFUSED: ("run.failed", None),
    Mood.LISTENING: ("voice.listening", None),
    Mood.DELEGATING: ("agent.spawned", None),
    Mood.FOCUSED: ("tool.called", None),
    Mood.CAREFUL: ("tool.called", {"untrusted": True}),
    Mood.THINKING: ("step.started", None),
    Mood.REMEMBERING: ("memory.proposed", None),
    Mood.DELIGHTED: ("run.finished", {"status": "ok"}),
}
PRIORITY = list(TRIGGERS)  # declared highest to lowest


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def engine(clock: FakeClock) -> MoodEngine:
    return MoodEngine(clock=clock)


def trigger(mood: Mood, run_id: str = "run-1") -> HaloEvent:
    type_, payload = TRIGGERS[mood]
    return ev(type_, payload, run_id)


def moods(events: list[HaloEvent]) -> list[str]:
    return [e.payload["mood"] for e in events]


# --- the trigger table ------------------------------------------------------


def test_engine_starts_idle(engine: MoodEngine) -> None:
    assert engine.current is Mood.IDLE


def test_mood_enum_has_the_thirteen_moods() -> None:
    assert {m.value for m in Mood} == {
        "asleep", "waking", "idle", "listening", "thinking", "focused",
        "delegating", "careful", "remembering", "asking", "guarding",
        "delighted", "confused",
    }  # fmt: skip


@pytest.mark.parametrize(
    ("type_", "payload", "expected"),
    [
        ("voice.listening", None, Mood.LISTENING),
        ("run.started", None, Mood.THINKING),
        ("step.started", None, Mood.THINKING),
        ("tool.called", None, Mood.FOCUSED),
        ("agent.spawned", None, Mood.DELEGATING),
        ("tool.called", {"untrusted": True}, Mood.CAREFUL),
        ("memory.proposed", None, Mood.REMEMBERING),
        ("memory.saved", None, Mood.REMEMBERING),
        ("approval.requested", None, Mood.ASKING),
        ("policy.blocked", None, Mood.GUARDING),
        ("run.finished", {"status": "ok"}, Mood.DELIGHTED),
        ("run.failed", None, Mood.CONFUSED),
    ],
)
def test_trigger_moves_idle_engine_to_expected_mood(
    engine: MoodEngine, type_: str, payload: dict | None, expected: Mood
) -> None:
    out = engine.feed(ev(type_, payload, run_id="run-42"))

    assert len(out) == 1
    event = out[0]
    assert event.type == "mood"
    assert event.run_id == "run-42"
    assert event.payload == {"mood": expected.value, "previous": "idle"}
    assert event.title == expected.value.capitalize()
    assert engine.current is expected


def test_no_mood_event_when_mood_does_not_change(
    engine: MoodEngine, clock: FakeClock
) -> None:
    engine.feed(ev("step.started"))
    clock.advance(DWELL_OK)

    assert engine.feed(ev("step.started")) == []
    assert engine.current is Mood.THINKING


def test_unrelated_events_never_emit_mood(engine: MoodEngine) -> None:
    for type_ in ("cost.updated", "egress.sent", "voice.heard", "mood"):
        assert engine.feed(ev(type_)) == []
    assert engine.current is Mood.IDLE


# --- priority ---------------------------------------------------------------

PAIRS = list(combinations(PRIORITY, 2))  # (higher, lower), in priority order


@pytest.mark.parametrize(("high", "low"), PAIRS, ids=[f"{h}>{lo}" for h, lo in PAIRS])
def test_lower_priority_event_does_not_displace_active_higher_mood(
    engine: MoodEngine, clock: FakeClock, high: Mood, low: Mood
) -> None:
    if (high, low) == (Mood.THINKING, Mood.DELIGHTED):
        pytest.skip("run.finished ends the run, releasing Thinking; see dedicated test")
    engine.feed(trigger(high))
    clock.advance(DWELL_OK)

    out = engine.feed(trigger(low))

    assert out == []
    assert engine.current is high


@pytest.mark.parametrize(("high", "low"), PAIRS, ids=[f"{h}>{lo}" for h, lo in PAIRS])
def test_higher_priority_event_displaces_active_lower_mood(
    engine: MoodEngine, clock: FakeClock, high: Mood, low: Mood
) -> None:
    engine.feed(trigger(low))
    clock.advance(DWELL_OK)

    engine.feed(trigger(high))

    assert engine.current is high


def test_finishing_a_run_releases_thinking_into_delighted(
    engine: MoodEngine, clock: FakeClock
) -> None:
    engine.feed(ev("step.started"))
    clock.advance(DWELL_OK)

    out = engine.feed(ev("run.finished", {"status": "ok"}))

    assert moods(out) == ["delighted"]


# --- approvals --------------------------------------------------------------


def test_asking_bypasses_dwell(engine: MoodEngine, clock: FakeClock) -> None:
    # A permission request must never wait behind the 700 ms dwell.
    engine.feed(ev("step.started"))
    clock.advance(TOO_SOON)

    out = engine.feed(ev("approval.requested"))

    assert moods(out) == ["asking"]
    assert out[0].payload["previous"] == "thinking"


def test_approval_resolved_releases_asking_to_idle_when_nothing_else_is_active(
    engine: MoodEngine, clock: FakeClock
) -> None:
    engine.feed(ev("approval.requested"))
    clock.advance(DWELL_OK)

    out = engine.feed(ev("approval.resolved"))

    assert moods(out) == ["idle"]
    assert out[0].payload["previous"] == "asking"


def test_approval_resolved_releases_asking_to_what_remaining_state_implies(
    engine: MoodEngine, clock: FakeClock
) -> None:
    engine.feed(ev("tool.called"))  # Focused
    clock.advance(DWELL_OK)
    engine.feed(ev("approval.requested"))
    clock.advance(DWELL_OK)

    out = engine.feed(ev("approval.resolved"))

    assert moods(out) == ["focused"]
    assert engine.current is Mood.FOCUSED


# --- dwell ------------------------------------------------------------------


def test_change_inside_dwell_is_deferred_then_emitted_by_tick(
    engine: MoodEngine, clock: FakeClock
) -> None:
    engine.feed(ev("step.started", run_id="run-7"))
    clock.advance(TOO_SOON)

    assert engine.feed(ev("tool.called", run_id="run-7")) == []
    assert engine.tick() == []
    assert engine.current is Mood.THINKING

    clock.advance(DWELL_OK - TOO_SOON)
    out = engine.tick()

    assert moods(out) == ["focused"]
    assert out[0].payload["previous"] == "thinking"
    assert out[0].run_id == "run-7"
    assert engine.current is Mood.FOCUSED


def test_deferred_change_stays_quiet_until_dwell_elapses(
    engine: MoodEngine, clock: FakeClock
) -> None:
    engine.feed(ev("step.started"))
    clock.advance(0.5)
    engine.feed(ev("tool.called"))

    clock.advance(0.125)  # 0.625 s since the change, still under 0.7

    assert engine.tick() == []


def test_highest_priority_pending_mood_wins_when_dwell_elapses(
    engine: MoodEngine, clock: FakeClock
) -> None:
    engine.feed(ev("step.started"))
    clock.advance(0.125)
    engine.feed(ev("tool.called"))  # Focused, pending
    engine.feed(ev("agent.spawned"))  # Delegating, pending, outranks Focused
    engine.feed(ev("voice.listening"))  # Listening, pending, outranks both
    clock.advance(DWELL_OK)

    out = engine.tick()

    assert moods(out) == ["listening"]


def test_pending_change_that_is_cancelled_before_dwell_emits_nothing(
    engine: MoodEngine, clock: FakeClock
) -> None:
    engine.feed(ev("step.started"))
    clock.advance(TOO_SOON)
    engine.feed(ev("tool.called"))
    engine.feed(ev("tool.result"))  # Focused released before it ever showed
    clock.advance(DWELL_OK)

    assert engine.tick() == []
    assert engine.current is Mood.THINKING


# --- timed moods ------------------------------------------------------------


def test_delighted_returns_to_idle_after_two_seconds(
    engine: MoodEngine, clock: FakeClock
) -> None:
    engine.feed(ev("run.finished", {"status": "ok"}))

    clock.advance(1.5)
    assert engine.tick() == []
    assert engine.current is Mood.DELIGHTED

    clock.advance(0.5)
    out = engine.tick()

    assert moods(out) == ["idle"]
    assert out[0].payload["previous"] == "delighted"
    assert engine.current is Mood.IDLE


@pytest.mark.parametrize("status", ["error", "denied"])
def test_unsuccessful_run_finished_is_not_delighted(
    engine: MoodEngine, clock: FakeClock, status: str
) -> None:
    engine.feed(ev("step.started"))
    clock.advance(DWELL_OK)

    out = engine.feed(ev("run.finished", {"status": status}))
    clock.advance(3.0)
    out += engine.tick()

    assert "delighted" not in moods(out)
    assert engine.current is Mood.IDLE


# --- sleep and waking -------------------------------------------------------


def test_asleep_after_ten_minutes_without_events(
    engine: MoodEngine, clock: FakeClock
) -> None:
    engine.feed(ev("run.finished", {"status": "ok"}))
    clock.advance(2.0)
    engine.tick()  # Delighted -> Idle

    clock.advance(597.0)  # 599 s since the last event
    assert engine.tick() == []
    assert engine.current is Mood.IDLE

    clock.advance(1.0)  # 600 s since the last event
    out = engine.tick()

    assert moods(out) == ["asleep"]
    assert out[0].payload["previous"] == "idle"
    assert engine.current is Mood.ASLEEP


def test_first_event_after_sleep_wakes_before_showing_its_own_mood(
    engine: MoodEngine, clock: FakeClock
) -> None:
    clock.advance(600.0)
    engine.tick()
    assert engine.current is Mood.ASLEEP

    out = engine.feed(ev("step.started"))

    assert moods(out) == ["waking"]
    assert out[0].payload["previous"] == "asleep"
    assert engine.current is Mood.WAKING

    clock.advance(DWELL_OK)
    out = engine.tick()

    assert moods(out) == ["thinking"]
    assert out[0].payload["previous"] == "waking"


# --- edge cases added by the test author (2) --------------------------------


def test_edge_asking_stays_until_every_pending_approval_is_resolved(
    engine: MoodEngine, clock: FakeClock
) -> None:
    """EDGE 1: two parallel sub-agents each ask; resolving one must not release Asking."""
    engine.feed(ev("approval.requested"))
    engine.feed(ev("approval.requested"))
    clock.advance(DWELL_OK)

    assert engine.feed(ev("approval.resolved")) == []
    assert engine.current is Mood.ASKING

    out = engine.feed(ev("approval.resolved"))
    assert moods(out) == ["idle"]


def test_edge_guarding_and_confused_clear_when_the_next_run_starts(
    engine: MoodEngine, clock: FakeClock
) -> None:
    """EDGE 2: Guarding is held for its run, not forever; a new run starts fresh."""
    engine.feed(ev("policy.blocked", run_id="run-1"))
    clock.advance(DWELL_OK)

    out = engine.feed(ev("run.started", run_id="run-2"))

    assert moods(out) == ["thinking"]
    assert out[0].run_id == "run-2"


# --- timed moods count from when they are shown, not from the event ---------


@pytest.mark.parametrize(
    ("trigger_type", "payload", "mood"),
    [
        ("run.finished", {"status": "ok"}, Mood.DELIGHTED),
        ("memory.saved", None, Mood.REMEMBERING),
    ],
)
def test_a_timed_mood_keeps_its_full_two_seconds_when_the_dwell_delays_it(
    engine: MoodEngine,
    clock: FakeClock,
    trigger_type: str,
    payload: dict | None,
    mood: Mood,
) -> None:
    engine.feed(ev("tool.called"))  # Focused, shown at t=0
    clock.advance(TOO_SOON)
    assert engine.feed(ev("tool.result")) == []  # Idle wanted, but held by the dwell
    engine.feed(ev(trigger_type, payload))  # the timed mood is wanted too
    clock.advance(0.5)  # t=0.75: the dwell is over, the timed mood is shown now
    assert moods(engine.tick()) == [mood.value]

    clock.advance(1.5)  # 1.5 s after it was shown
    assert engine.tick() == []
    assert engine.current is mood

    clock.advance(0.5)  # 2.0 s after it was shown
    assert moods(engine.tick()) == ["idle"]
