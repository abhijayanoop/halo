"""memory.recall: answer from the vault, with a link to each note used."""

import asyncio

from halo.core.context import HaloContext
from halo.core.contracts import RunContext
from halo.skills.errors import SkillArgsError

_UNKNOWN = "I don't know. Nothing in your notes matches that."


async def run(ctx: RunContext, args: dict) -> dict:
    if not isinstance(ctx, HaloContext):
        raise TypeError("memory.recall needs a HaloContext")
    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise SkillArgsError("memory.recall needs a non-empty 'query' string")
    memory = ctx.memory
    if memory is None:
        return {"answer": "Memory isn't set up.", "sources": [], "error": "no memory"}

    found = await asyncio.to_thread(memory.recall, query)
    if not found:
        return {"answer": _UNKNOWN, "sources": []}

    sources = []
    lines = []
    for item in found:
        link = memory.link(item)
        hint = " (hint)" if item.trust == "low" or item.source != "you" else ""
        sources.append(
            {
                "fact": item.fact,
                "note": item.note_path,
                "link": link,
                "source": item.source,
                "trust": item.trust,
            }
        )
        lines.append(f"- {item.fact}{hint}: {link}")
    return {"answer": "From your notes:\n" + "\n".join(lines), "sources": sources}
