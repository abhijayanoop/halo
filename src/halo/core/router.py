"""The router: turn a request into an Intent (which skill, which args).

Nano answers first; low confidence or invalid output escalates to Super through
the cascade. "Let's get to work" never reaches a model.
"""

import re
from typing import get_args

from halo.core.contracts import Intent, SkillName
from halo.models.cascade import cascade_call
from halo.models.client import ModelClient

_SKILLS = {
    "chat": "Conversation or a general question. args: message (the user's words).",
    "app.open": "Open an app, file, folder or URL. args: app (the name as spoken).",
    "code.task": (
        "Work on code in a repo: explain, plan or change it. "
        "args: task (what to do), mode (explain | plan | implement) if clear."
    ),
    "trip.plan": (
        "Research and plan a trip. args: destination, days, month, budget (omit what was not said)."
    ),
    "expense.log": "Record money the user spent. args: text (the user's words, unchanged).",
    "expense.query": "Answer a question about past spending. args: text (the user's words, unchanged).",
    "memory.remember": "Store a fact the user wants kept. args: fact.",
    "memory.recall": "Answer from what the user told Halo earlier, or open a saved note. args: query.",
    "memory.forget": "Delete something Halo remembers. args: query.",
    "work.start": "Start a work session: recall where the user stopped and propose tasks. args: none.",
}

assert set(_SKILLS) == set(get_args(SkillName)), "router prompt is missing a skill"

_SYSTEM = (
    "You are the router for Halo, a personal desktop assistant. Pick the one skill that "
    "handles the user's request and fill in its args.\n\n"
    "Skills:\n"
    + "\n".join(f"- {name}: {desc}" for name, desc in _SKILLS.items())
    + '\n\nReply with JSON only: {"skill": ..., "args": {...}, "confidence": 0.0-1.0}. '
    "confidence is how sure you are that this is the right skill. Use below 0.7 when the "
    "request fits more than one skill or is unclear. Use chat only when no other skill fits."
)

_WORK_START_PHRASES = {"lets get to work", "lets get started"}


def _normalize(text: str) -> str:
    text = text.casefold().replace("'", "").replace("’", "")
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


async def route(
    client: ModelClient,
    request: str,
    *,
    run_id: str | None = None,
    context: str = "",
) -> Intent:
    if _normalize(request) in _WORK_START_PHRASES:
        return Intent(skill="work.start", args={}, confidence=1.0)

    system = _SYSTEM
    if context:
        system += f"\n\nWhat you know, with sources:\n{context}"
    result = await cascade_call(
        client,
        [{"role": "system", "content": system}, {"role": "user", "content": request}],
        Intent,
        run_id=run_id,
    )
    return result.parsed
