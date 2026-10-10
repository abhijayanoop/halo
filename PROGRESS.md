# Progress
_Last updated: 2026-10-10 by /handoff_

## Done
- Day 1 scaffold: CLAUDE.md, .claude/ (rules, hooks, agents, skills), docs/ skeleton, PROGRESS.md, .worktreeinclude.
- `halo/core/contracts.py`: all 13 frozen contracts (Pydantic v2), `export_schemas.py` + schemas/ staleness test, docs/CONTRACTS.md.
- Day 0 spikes, all closed out in `spikes/RESULTS.md`:
  - ASR latency resolved (Parakeet CTC 110M int8, <200ms decode incl. live mic); accuracy not resolved (transducer variant fails to load - sherpa-onnx incompatibility; VAD trimming fixed a real bug but didn't fix accuracy). Decision: typing/push-to-talk primary for v0.1.
  - pywebview confirmed working (frameless, always-on-top, JS resize) on Windows.
  - claude-agent-sdk confirmed working against `tests/fixtures/demo_repo` (streaming + `can_use_tool` both verified).
- Public repo created: https://github.com/abhijayanoop/halo
- `.github/workflows/ci.yml` (ruff, pyright, pytest, gitleaks) - PR #1, both push and pull_request runs green.

## In progress
- PR #1 (`ci/github-actions`) open, not merged — next step: review and merge, then delete the branch.

## Next
- Day 1 S2: spec interview session (docs/SPEC.md already drafted this session from an earlier interview; re-check it's still current before Day 2).
- Day 1 S3 gate gap: `halo/core/contracts.py` is committed but the gate also wants `schemas/` export verified in CI (it is, via the pytest staleness test) — no action needed, just confirming.
- Day 2: router/planner/executor + event bus (`halo/core/graph.py`, `halo/api/`).
- Revisit voice accuracy later (non-quantized ASR model) if time allows — not launch-blocking.

## Known issues
- Voice transcription accuracy is weak on live mic input even after VAD fixes; see `spikes/RESULTS.md` for the two failed fix attempts and why.
- `sherpa-onnx`'s `OfflineRecognizer.from_transducer` cannot load the NeMo Parakeet TDT transducer export in the installed version (metadata error) - don't retry this path without checking for a newer sherpa-onnx release first.
- `tests/fixtures/demo_repo` is gitignored (has its own nested `.git`) - regenerate locally per `spikes/claude_worker_probe.py`'s docstring if it's missing.

## How to run
- `uv sync && uv run python -m halo.core.export_schemas` (schemas/ already committed, re-run only after a contracts change)
- `uv run pytest -m "not live" -q` · `uv run ruff check . --fix` · `uv run ruff format .` · `uv run pyright`
- Spikes (ephemeral deps, see each file's docstring): `uv run --no-project --with sherpa-onnx --with soundfile --with numpy python spikes/voice_asr.py --wav <path>`
