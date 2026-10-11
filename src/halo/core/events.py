"""Helpers for stamping HaloEvents: ULID ids and UTC timestamps."""

import secrets
import time
from datetime import UTC, datetime

from halo.core.contracts import HaloEvent, HaloEventType

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _now_ms() -> int:
    return time.time_ns() // 1_000_000


def new_event_id() -> str:
    """A 26-char ULID: 48-bit millisecond timestamp + 80 random bits, so ids
    sort by creation time."""
    value = (_now_ms() << 80) | secrets.randbits(80)
    return "".join(_CROCKFORD[(value >> shift) & 31] for shift in range(125, -1, -5))


def make_event(
    run_id: str,
    type: HaloEventType,
    title: str,
    *,
    payload: dict | None = None,
    agent_id: str | None = None,
    parent_agent_id: str | None = None,
) -> HaloEvent:
    return HaloEvent(
        id=new_event_id(),
        run_id=run_id,
        ts=datetime.now(UTC),
        type=type,
        agent_id=agent_id,
        parent_agent_id=parent_agent_id,
        title=title,
        payload=payload or {},
    )
