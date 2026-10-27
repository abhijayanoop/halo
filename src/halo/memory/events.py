"""The events that carry proposed memories to the HUD. They belong to no run, so
they share one id: the HUD keys proposals by `candidate_id`, not by run."""

from halo.core.contracts import HaloEvent, MemoryCandidate, MemoryItem
from halo.core.events import make_event

INBOX_RUN = "memory"


def proposed_event(candidate_id: str, candidate: MemoryCandidate) -> HaloEvent:
    return make_event(
        INBOX_RUN,
        "memory.proposed",
        f"Worth remembering: {candidate.fact[:60]}",
        payload={
            "candidate_id": candidate_id,
            "fact": candidate.fact,
            "subject": candidate.subject,
            "source": candidate.source,
            "trust": candidate.trust,
        },
    )


def approved_event(candidate_id: str, item: MemoryItem) -> HaloEvent:
    return make_event(
        INBOX_RUN,
        "memory.saved",
        f"Remembered: {item.fact[:60]}",
        payload={
            "candidate_id": candidate_id,
            "fact": item.fact,
            "source": item.source,
            "trust": item.trust,
            "note": item.note_path,
            "block_id": item.block_id,
        },
    )


def rejected_event(candidate_id: str) -> HaloEvent:
    return make_event(
        INBOX_RUN,
        "memory.forgotten",
        "Discarded a proposed memory",
        payload={"candidate_id": candidate_id, "rejected": True},
    )
