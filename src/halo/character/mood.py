"""Event -> mood rules for Halo's character.

Mood is decided here, in Python, from the event stream; the HUD only animates
it. The engine keeps a set of active conditions, shows the highest-priority
one, and holds every mood on screen for at least DWELL_S so the face never
flickers. The clock is injected so the rules are testable without sleeping.
"""

import time
from collections.abc import Callable
from enum import StrEnum

from halo.core.contracts import HaloEvent
from halo.core.events import make_event

DWELL_S = 0.7  # minimum time a mood stays on screen
# Moods that fade by themselves, and how long each stays once it is shown.
HOLD_S = {
    "delighted": 2.0,
    "remembering": 2.0,
    "confused": 6.0,
    "guarding": 6.0,
}
SLEEP_AFTER_S = 600.0  # no events for 10 minutes -> Asleep


class Mood(StrEnum):
    ASLEEP = "asleep"
    WAKING = "waking"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    FOCUSED = "focused"
    DELEGATING = "delegating"
    CAREFUL = "careful"
    REMEMBERING = "remembering"
    ASKING = "asking"
    GUARDING = "guarding"
    DELIGHTED = "delighted"
    CONFUSED = "confused"


# Highest priority first. A permission request always wins.
PRIORITY: tuple[Mood, ...] = (
    Mood.ASKING,
    Mood.GUARDING,
    Mood.CONFUSED,
    Mood.LISTENING,
    Mood.DELEGATING,
    Mood.FOCUSED,
    Mood.CAREFUL,
    Mood.THINKING,
    Mood.REMEMBERING,
    Mood.DELIGHTED,
)


class MoodEngine:
    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._current = Mood.IDLE
        self._last_change: float | None = None  # the initial Idle has no dwell
        self._last_event = clock()
        self._run_id = "mood"
        # Active conditions.
        self._listening = False
        self._thinking = False
        self._focused = 0
        self._careful = 0
        self._delegating = 0
        self._asking = 0
        # Timed moods: wanted (`pending`) from the event, but the hold only starts
        # once the face is actually shown, so the dwell cannot eat into it.
        self._pending: set[Mood] = set()
        self._until: dict[Mood, float] = {}
        # The event that last asked for each mood: its title is the status line.
        self._causes: dict[Mood, HaloEvent] = {}

    @property
    def current(self) -> Mood:
        return self._current

    def cause(self, mood: Mood) -> HaloEvent | None:
        """The latest event that asked for `mood` (what its status line is about)."""
        return self._causes.get(mood)

    def feed(self, event: HaloEvent) -> list[HaloEvent]:
        if event.type in ("mood", "cost.updated"):  # not activity: never wakes Halo
            return []
        now = self._clock()
        self._expire(now)
        self._last_event = now
        self._run_id = event.run_id
        self._apply(event, now)
        if self._current is Mood.ASLEEP:
            # Asking never waits; everything else wakes up first and shows
            # the mood it implies once the dwell has elapsed (via tick()).
            target = Mood.ASKING if self._asking else Mood.WAKING
            return self._switch(target, now)
        return self._reconcile(now)

    def tick(self) -> list[HaloEvent]:
        now = self._clock()
        self._expire(now)
        if (
            self._current is Mood.IDLE
            and self._desired() is Mood.IDLE
            and now - self._last_event >= SLEEP_AFTER_S
            and self._dwell_elapsed(now)
        ):
            return self._switch(Mood.ASLEEP, now)
        return self._reconcile(now)

    # -- rules ---------------------------------------------------------------

    def _want(self, mood: Mood, event: HaloEvent) -> None:
        self._causes[mood] = event

    def _apply(self, event: HaloEvent, now: float) -> None:
        match event.type:
            case "voice.listening":
                self._listening = True
                self._want(Mood.LISTENING, event)
            case "voice.heard":
                self._listening = False
            case "run.started":
                # A new run starts fresh: stale blocks and counters are dropped.
                for mood in (Mood.GUARDING, Mood.CONFUSED, Mood.DELIGHTED):
                    self._pending.discard(mood)
                    self._until.pop(mood, None)
                self._focused = self._careful = self._delegating = 0
                self._thinking = True
                self._want(Mood.THINKING, event)
            case "step.started":
                self._thinking = True
                self._want(Mood.THINKING, event)
            case "tool.called":
                if event.payload.get("untrusted") is True:
                    self._careful += 1
                    self._want(Mood.CAREFUL, event)
                else:
                    self._focused += 1
                    self._want(Mood.FOCUSED, event)
            case "tool.result":
                self._release_tool(event.payload.get("untrusted") is True)
            case "agent.spawned":
                self._delegating += 1
                self._want(Mood.DELEGATING, event)
            case "agent.finished":
                self._delegating = max(0, self._delegating - 1)
            case "memory.proposed" | "memory.saved":
                self._pending.add(Mood.REMEMBERING)
                self._want(Mood.REMEMBERING, event)
            case "approval.requested":
                self._asking += 1
                self._want(Mood.ASKING, event)
            case "approval.resolved":
                self._asking = max(0, self._asking - 1)
            case "policy.blocked":
                self._pending.add(Mood.GUARDING)
                self._want(Mood.GUARDING, event)
            case "run.failed":
                self._thinking = False
                self._pending.add(Mood.CONFUSED)
                self._want(Mood.CONFUSED, event)
            case "run.finished":
                self._thinking = False
                if event.payload.get("status") == "ok":
                    self._pending.add(Mood.DELIGHTED)
                    self._want(Mood.DELIGHTED, event)

    def _release_tool(self, untrusted: bool) -> None:
        if (untrusted and self._careful) or not self._focused:
            self._careful = max(0, self._careful - 1)
        else:
            self._focused -= 1

    def _expire(self, now: float) -> None:
        for mood in [m for m, until in self._until.items() if now >= until]:
            del self._until[mood]

    def _active(self, mood: Mood) -> bool:
        match mood:
            case Mood.ASKING:
                return self._asking > 0
            case Mood.LISTENING:
                return self._listening
            case Mood.DELEGATING:
                return self._delegating > 0
            case Mood.FOCUSED:
                return self._focused > 0
            case Mood.CAREFUL:
                return self._careful > 0
            case Mood.THINKING:
                return self._thinking
            case Mood.GUARDING | Mood.CONFUSED | Mood.REMEMBERING | Mood.DELIGHTED:
                return mood in self._pending or mood in self._until
            case _:
                return False

    def _desired(self) -> Mood:
        return next((m for m in PRIORITY if self._active(m)), Mood.IDLE)

    # -- transitions ---------------------------------------------------------

    def _dwell_elapsed(self, now: float) -> bool:
        return self._last_change is None or now - self._last_change >= DWELL_S

    def _reconcile(self, now: float) -> list[HaloEvent]:
        if self._current is Mood.ASLEEP:
            return []  # only an incoming event wakes Halo
        target = self._desired()
        if target is self._current:
            return []
        # A permission request must never wait behind the dwell.
        if target is Mood.ASKING or self._dwell_elapsed(now):
            return self._switch(target, now)
        return []  # deferred: the conditions are re-read on the next tick

    def _switch(self, target: Mood, now: float) -> list[HaloEvent]:
        if target is self._current:
            return []
        previous = self._current
        self._current = target
        self._last_change = now
        if target.value in HOLD_S:
            self._pending.discard(target)
            self._until[target] = now + HOLD_S[target.value]
        return [
            make_event(
                self._run_id,
                "mood",
                target.value.capitalize(),
                payload={"mood": target.value, "previous": previous.value},
            )
        ]
