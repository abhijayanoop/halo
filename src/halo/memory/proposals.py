"""Proposed memories: bullets in `Inbox/proposed-memories.md`.

A proposal is not a memory. It waits there, with its subject and where it came
from, until the user approves it (it is then written to a real note) or rejects
it. The inbox folder is never indexed, so a proposal can never be recalled.
"""

import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import get_args

from halo.core.contracts import MemoryCandidate, MemorySource, TrustLevel
from halo.memory.vault import _BULLET, _clean_fact, _fields, _line_id, _read


def append_proposal(path: Path, candidate: MemoryCandidate, now: datetime) -> str:
    """List a proposed memory in the inbox note. Returns its id (`^p-...`)."""
    fact = _clean_fact(candidate.fact)
    subject = _clean_fact(candidate.subject)
    if not fact:
        raise ValueError("a proposal needs some text")
    text = _read(path) if path.exists() else ""
    path.parent.mkdir(parents=True, exist_ok=True)
    eol = "\r\n" if "\r\n" in text else "\n"
    existing = set(re.findall(r"\^([A-Za-z0-9-]+)\s*$", text, re.MULTILINE))
    block = f"p-{secrets.token_hex(2)}"
    while block in existing:
        block = f"p-{secrets.token_hex(3)}"
    line = (
        f"- {fact} [subject:: {subject}] [src:: {candidate.source}] "
        f"[trust:: {candidate.trust}] [at:: {now.date().isoformat()}] ^{block}"
    )
    if text and not text.endswith(("\n", "\r")):
        text += eol
    path.write_bytes((text + line + eol).encode("utf-8"))
    return f"^{block}"


def list_proposals(path: Path) -> list[tuple[str, MemoryCandidate]]:
    """The proposals waiting in the inbox note, oldest first, as (id, candidate)."""
    try:
        text = _read(path)
    except OSError:
        return []
    found: list[tuple[str, MemoryCandidate]] = []
    for line in text.splitlines():
        bullet = _BULLET.match(line)
        if not bullet:
            continue
        fact, fields, explicit = _fields(bullet["body"])
        source, trust = fields.get("src"), fields.get("trust")
        if not fact or source not in get_args(MemorySource):
            continue
        found.append(
            (
                _line_id(fact, explicit),
                MemoryCandidate(
                    fact=fact,
                    subject=fields.get("subject", ""),
                    source=source,  # type: ignore[arg-type]
                    trust=trust if trust in get_args(TrustLevel) else "low",  # type: ignore[arg-type]
                ),
            )
        )
    return found
