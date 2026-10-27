"""code.task: a coding session, from brief to merge, supervised by Halo."""

import asyncio

from halo.coding.session import run_code_task
from halo.core.context import HaloContext
from halo.core.contracts import RunContext
from halo.memory.retrieve import assemble_context


async def run(ctx: RunContext, args: dict) -> dict:
    if not isinstance(ctx, HaloContext):
        raise TypeError("code.task needs a HaloContext")
    if ctx.code is None:
        return {"error": "Coding sessions are not set up."}
    memory_context = ""
    task = args.get("task")
    if ctx.memory is not None and isinstance(task, str) and task.strip():
        found = await asyncio.to_thread(ctx.memory.recall, task)
        memory_context = assemble_context(found).text  # never a privacy: local fact
    return await run_code_task(
        ctx.model, ctx.code, ctx.emit, ctx.run_id, args, memory_context=memory_context
    )
