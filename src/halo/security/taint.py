"""Taint tracking: a value derived from untrusted content stays wrapped."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Tainted[T]:
    """A value that came from, or was derived from, untrusted content."""

    value: T = field(repr=False)
    source: str
    url: str | None = None

    def __repr__(self) -> str:
        return f"Tainted(source={self.source!r}, url={self.url!r})"

    __str__ = __repr__


def contains_taint(obj: Any) -> bool:
    """True if a Tainted value appears anywhere in nested arguments."""
    if isinstance(obj, Tainted):
        return True
    if isinstance(obj, Mapping):
        return any(contains_taint(k) or contains_taint(v) for k, v in obj.items())
    if isinstance(obj, (list, tuple, set, frozenset)):
        return any(contains_taint(v) for v in obj)
    return False
