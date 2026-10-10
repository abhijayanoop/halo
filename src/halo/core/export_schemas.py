"""Export JSON Schema for every contract model in halo.core.contracts.

Run as `python -m halo.core.export_schemas` to (re)write schemas/. Run with
`--check` to report whether schemas/ is stale without touching it.
"""

import json
import logging
import sys
import tempfile
from pathlib import Path

from pydantic import BaseModel

from halo.core import contracts

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_DIR = REPO_ROOT / "schemas"


def discover_models() -> list[type[BaseModel]]:
    """Every concrete contract model defined in halo.core.contracts,
    sorted by name. Protocols (RunContext, Skill) aren't BaseModel
    subclasses, so they're excluded automatically."""
    found = []
    for obj in vars(contracts).values():
        if not isinstance(obj, type):
            continue
        if not issubclass(obj, BaseModel):
            continue
        if obj in (BaseModel, contracts.HaloModel):
            continue
        if obj.__module__ != contracts.__name__:
            continue
        found.append(obj)
    return sorted(found, key=lambda m: m.__name__)


def export_all(out_dir: Path) -> dict[str, str]:
    """Write one <ModelName>.schema.json per contract model into out_dir.

    Clears pre-existing *.schema.json files first so a renamed or removed
    model doesn't leave an orphan behind. Returns {filename: contents} for
    what was written.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob("*.schema.json"):
        stale.unlink()

    written: dict[str, str] = {}
    for model in discover_models():
        schema = model.model_json_schema()
        content = json.dumps(schema, indent=2, sort_keys=True) + "\n"
        filename = f"{model.__name__}.schema.json"
        (out_dir / filename).write_text(content, encoding="utf-8")
        written[filename] = content
    return written


def find_stale(committed_dir: Path, fresh: dict[str, str]) -> list[str]:
    """Describe every mismatch between the schemas/ committed to the repo
    and a freshly generated set. Empty list means they're in sync."""
    committed = {
        p.name: p.read_text(encoding="utf-8")
        for p in committed_dir.glob("*.schema.json")
    }
    problems = []
    for name in sorted(set(committed) | set(fresh)):
        if name not in fresh:
            problems.append(
                f"{name}: present in {committed_dir} but no longer a contract model"
            )
        elif name not in committed:
            problems.append(
                f"{name}: missing from {committed_dir}; model has no committed schema"
            )
        elif committed[name] != fresh[name]:
            problems.append(f"{name}: committed schema differs from the current model")
    return problems


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv

    if "--check" in args:
        with tempfile.TemporaryDirectory() as tmp:
            fresh = export_all(Path(tmp))
            problems = find_stale(SCHEMAS_DIR, fresh)
        if problems:
            for problem in problems:
                logger.error(problem)
            return 1
        logger.info("schemas/ is up to date with %d contract models", len(fresh))
        return 0

    written = export_all(SCHEMAS_DIR)
    logger.info("exported %d schemas to %s", len(written), SCHEMAS_DIR)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
