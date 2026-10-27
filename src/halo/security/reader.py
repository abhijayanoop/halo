"""The one place untrusted text is wrapped and read.

Minimal version: wrapping, sanitising and schema-validated extraction. The
quarantined Nano Reader (no tools, strict output schema) is built on top of
`extract` on the security day; nothing else may unwrap a Tainted value.
"""

import re

from pydantic import BaseModel

from halo.security.taint import Tainted

MAX_UNTRUSTED_CHARS = 20_000

_CONTROL = re.compile(r"\x1b\[[0-9;]*[A-Za-z]|[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def wrap_untrusted(text: str, *, source: str, url: str | None = None) -> Tainted[str]:
    """Wrap text from the web, a fetched file or Claude Code output."""
    clean = _CONTROL.sub("", text)[:MAX_UNTRUSTED_CHARS]
    return Tainted(clean, source=source, url=url)


def extract[M: BaseModel](data: Tainted[str], schema: type[M]) -> Tainted[M]:
    """Validate untrusted JSON text against a strict schema; the result stays Tainted.

    Raises pydantic.ValidationError on anything that is not exactly the schema.
    """
    parsed = schema.model_validate_json(data.value, strict=True)
    return Tainted(parsed, source=data.source, url=data.url)
