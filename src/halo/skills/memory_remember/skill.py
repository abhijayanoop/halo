"""memory.remember: write a fact the user stated to their vault, as `src:: you`."""

import asyncio

from halo.core.context import HaloContext
from halo.core.contracts import RunContext
from halo.core.events import make_event
from halo.memory.store import DEFAULT_NOTE
from halo.memory.vault import VaultPathError
from halo.skills.errors import SkillArgsError


async def run(ctx: RunContext, args: dict) -> dict:
    if not isinstance(ctx, HaloContext):
        raise TypeError("memory.remember needs a HaloContext")
    fact = args.get("fact")
    if not isinstance(fact, str) or not fact.strip():
        raise SkillArgsError("memory.remember needs a non-empty 'fact' string")
    note = args.get("note", DEFAULT_NOTE)
    if not isinstance(note, str) or not note.strip():
        raise SkillArgsError("'note' must be a note path like Projects/halo.md")
    if ctx.memory is None:
        return {"saved": False, "error": "memory isn't set up"}

    try:
        item = await asyncio.to_thread(ctx.memory.remember, fact, note=note.strip())
    except (VaultPathError, ValueError) as exc:
        raise SkillArgsError(str(exc)) from exc

    ctx.emit(
        make_event(
            ctx.run_id,
            "memory.saved",
            f"Remembered: {item.fact[:60]}",
            payload={
                "fact": item.fact,
                "source": item.source,
                "trust": item.trust,
                "note": item.note_path,
                "block_id": item.block_id,
            },
        )
    )
    return {"saved": True, "note": item.note_path, "block_id": item.block_id}
