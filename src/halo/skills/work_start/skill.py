"""work.start: where you stopped, and what to pick up, straight from the vault."""

import asyncio
from datetime import date

from halo.core.context import HaloContext
from halo.core.contracts import RunContext
from halo.memory.worksession import Proposal, plan_work

_NOTHING = (
    "I don't see anything open in your notes. Tell me what you want to work on, "
    "or add `- [ ]` tasks to today's journal or a project note."
)


def _answer(stopped_at: str, proposals: list[Proposal]) -> str:
    lines = []
    if stopped_at:
        lines.append(f"You stopped at: {stopped_at}.")
    if not proposals:
        lines.append(_NOTHING)
        return "\n".join(lines)
    lines.append("Here is what I'd pick up:")
    for number, item in enumerate(proposals, start=1):
        where = f" ({item.project})" if item.project else ""
        lines.append(f"{number}. {item.title}{where}")
    return "\n".join(lines)


async def run(ctx: RunContext, args: dict) -> dict:
    # Arguments are ignored on purpose: nothing a request says can point this at another folder.
    if not isinstance(ctx, HaloContext):
        raise TypeError("work.start needs a HaloContext")
    if ctx.memory is None:
        return {"answer": "Memory isn't set up.", "proposals": [], "error": "no memory"}
    plan = await asyncio.to_thread(plan_work, ctx.memory.vault, date.today())
    return {
        "answer": _answer(plan.stopped_at, plan.proposals),
        "stopped_at": plan.stopped_at,
        "proposals": [
            {
                "title": p.title,
                "project": p.project,
                "request": p.request,
                "source": p.source,
            }
            for p in plan.proposals
        ],
    }
