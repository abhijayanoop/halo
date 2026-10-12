"""Status lines for the HUD bar: Nemotron Nano writes each one, and a template
covers every failure (too slow, an error, or a line that breaks the voice rules).

Voice rules: at most 7 words, present tense, specific nouns, no emoji, no
exclamation marks. Warm when things go well, plain and serious for permissions,
errors and money.
"""

import asyncio
import logging
import re

from halo.core.contracts import HaloEvent
from halo.models.client import (
    ConfigError,
    ModelClient,
    ModelUnavailableError,
    ModelValidationError,
    PrivacyViolationError,
)
from halo.models.transport import ModelRequestError, TransientModelError

logger = logging.getLogger(__name__)

MAX_WORDS = 7
MAX_CHARS = 60
TIMEOUT_S = 0.4

_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿️]")
_SERIOUS = {"approval.requested", "run.failed", "policy.blocked"}
_MODEL_TROUBLE = (
    TimeoutError,
    ConfigError,
    PrivacyViolationError,
    ModelValidationError,
    ModelUnavailableError,
    ModelRequestError,
    TransientModelError,
)

_SYSTEM = (
    "You write the one-line status shown on Halo's small desktop bar. "
    f"At most {MAX_WORDS} words, present tense, specific nouns "
    '("Comparing 14 hotels in Anjuna", never "Processing"). '
    "No emoji, no exclamation marks. Reply with the line only."
)
_SERIOUS_TONE = " Be plain and serious."
_WARM_TONE = " Be warm and a little playful."


def valid_line(line: str) -> bool:
    text = line.strip()
    return (
        bool(text)
        and "\n" not in text
        and len(text) <= MAX_CHARS
        and len(text.split()) <= MAX_WORDS
        and "!" not in text
        and not _EMOJI.search(text)
    )


def _clean(text: str) -> str:
    return text.strip().strip("\"'“”‘’").rstrip(".").strip()


def _shorten(title: str) -> str:
    """A title made to follow the voice rules: no emoji or '!', first 7 words."""
    cleaned = _EMOJI.sub("", title).replace("!", "")
    words = cleaned.split()[:MAX_WORDS]
    return " ".join(words)[:MAX_CHARS].strip() or "Working on it"


def template_line(event: HaloEvent) -> str:
    match event.type:
        case "run.started":
            return "Working on it"
        case "approval.resolved":
            return "Got it"
        case "policy.blocked":
            return "Blocked something suspicious"
        case "run.failed":
            return "That didn't work"
        case "run.finished":
            status = event.payload.get("status")
            if status == "denied":
                return "Stopped, as you asked"
            return "All done" if status == "ok" else "Finished with a problem"
        case "memory.proposed" | "memory.saved":
            return "Noting that down"
        case "voice.listening":
            return "Listening"
        case _:
            return _shorten(event.title)


def _tone(event: HaloEvent, skill: str | None) -> str:
    if event.type in _SERIOUS or (skill or "").startswith("expense"):
        return _SERIOUS_TONE
    if event.type == "run.finished" and event.payload.get("status") == "ok":
        return _WARM_TONE
    if event.type in {"memory.saved"}:
        return _WARM_TONE
    return ""


class StatusLines:
    def __init__(self, client: ModelClient, *, timeout_s: float = TIMEOUT_S) -> None:
        self._client = client
        self._timeout_s = timeout_s
        self._cache: dict[tuple[str | None, str, str], str] = {}

    async def line(self, event: HaloEvent, *, skill: str | None = None) -> str:
        """The status line for `event`. Never slower than the timeout, never
        raises: on any trouble the template is returned (and not cached, so a
        later attempt can still get a model line)."""
        key = (skill, event.type, event.title)
        if key in self._cache:
            return self._cache[key]
        try:
            result = await asyncio.wait_for(
                self._client.call(
                    "nano",
                    [
                        {"role": "system", "content": _SYSTEM + _tone(event, skill)},
                        {
                            "role": "user",
                            "content": (
                                f"Skill: {skill or 'none'}\nEvent: {event.type}\n"
                                f"Title: {event.title}"
                            ),
                        },
                    ],
                    run_id=event.run_id,
                ),
                self._timeout_s,
            )
            text = _clean(result.text)
        except _MODEL_TROUBLE as exc:  # a status line must never break a run
            logger.debug(
                "status line fell back to the template: %s", type(exc).__name__
            )
            return template_line(event)
        if not valid_line(text):
            return template_line(event)
        self._cache[key] = text
        return text
