from pathlib import Path

from halo.core.export_schemas import export_all, find_stale

REPO_ROOT = Path(__file__).resolve().parents[2]
COMMITTED_SCHEMAS_DIR = REPO_ROOT / "schemas"


def test_schemas_dir_matches_contracts(tmp_path: Path) -> None:
    fresh = export_all(tmp_path)
    problems = find_stale(COMMITTED_SCHEMAS_DIR, fresh)
    assert not problems, (
        "schemas/ is stale relative to halo/core/contracts.py. Run "
        "`uv run python -m halo.core.export_schemas` and commit the result.\n"
        + "\n".join(problems)
    )
