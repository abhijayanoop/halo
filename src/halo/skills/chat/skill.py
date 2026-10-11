"""chat: answer a message with Nano."""

from halo.core.context import HaloContext
from halo.core.contracts import RunContext

_SYSTEM = (
    "You are Halo, a friendly, private desktop assistant with a small hand-drawn "
    "character. Answer briefly and plainly. If you do not know, say so."
)


async def run(ctx: RunContext, args: dict) -> dict:
    if not isinstance(ctx, HaloContext):
        raise TypeError("chat needs a HaloContext with a model client")
    message = args.get("message")
    if not isinstance(message, str) or not message.strip():
        raise ValueError("chat needs a non-empty 'message' string")

    result = await ctx.model.call(
        "nano",
        [{"role": "system", "content": _SYSTEM}, {"role": "user", "content": message}],
        run_id=ctx.run_id,
    )
    return {"reply": result.text}
