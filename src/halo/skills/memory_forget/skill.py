"""memory.forget: delete matching lines from the vault, only once approved."""

import asyncio

from halo.core.context import HaloContext
from halo.core.contracts import RunContext
from halo.core.events import make_event
from halo.skills.errors import SkillArgsError

MAX_LINES = 3


def _query(args: dict) -> str:
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise SkillArgsError("memory.forget needs a non-empty 'query' string")
    return query.strip()


def describe(args: dict) -> str:
    """What the approval card shows: the validated query, never extra keys."""
    return f"Forget what I remember matching: {_query(args)} (up to {MAX_LINES} lines)"


def grantable(args: dict) -> bool:
    """Deleting needs its own yes every time."""
    return False


async def run(ctx: RunContext, args: dict) -> dict:
    if not isinstance(ctx, HaloContext):
        raise TypeError("memory.forget needs a HaloContext")
    query = _query(args)
    if getattr(ctx, "approved", False) is not True:  # set by the executor only
        return {"forgotten": [], "needs_approval": True}
    if ctx.memory is None:
        return {"forgotten": [], "error": "memory isn't set up"}

    gone = await asyncio.to_thread(ctx.memory.forget, query, max_items=MAX_LINES)
    for item in gone:
        ctx.emit(
            make_event(
                ctx.run_id,
                "memory.forgotten",
                f"Forgot: {item.fact[:60]}",
                payload={
                    "fact": item.fact,
                    "note": item.note_path,
                    "block_id": item.block_id,
                },
            )
        )
    return {
        "forgotten": [{"fact": i.fact, "note": i.note_path} for i in gone],
    }
