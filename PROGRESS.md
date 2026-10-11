# Progress
_Last updated: 2026-10-12. Day numbers are the user's: Day 1 = Oct 10 (scaffold, contracts, spikes), Day 2 = Oct 11 (core brain, PLAN.md "Day 1"), Day 3 = HUD and character (PLAN.md "Day 2")._

## Done
- Day 1: scaffold, frozen contracts + schema export, CI, spikes for ASR, pywebview and claude-agent-sdk (`spikes/RESULTS.md`).
- Day 2, built and tested offline (201 tests, branch `feat/core-day2`, 6 commits, not yet pushed):
  event bus + ULID events, flight recorder (`~/.halo/runs/*.jsonl`), skill registry + `chat` and `app.open`,
  config loader, model client (retry, backoff, ₹ cost, `privacy: local` guard) + Nano-to-Super cascade,
  state, router, planner, LangGraph graph with approval gate (interrupt/resume, survives restart),
  `HaloRunner`, FastAPI server (`/run`, `/approve`, `WS /events`, localhost-only), `halo` CLI, `open_halo()` wiring.

## In progress: finish Day 2 for real, then push, then Day 3
Built offline and committed: provider profiles (`token-factory` default, `nvidia-api` dev via `HALO_PROFILE`), structured-output
modes, `<think>` stripping, `spikes/list_models.py`, `spikes/tool_calling_probe.py` (hard call cap, refuses live without `--yes`).
Remaining, in order (ask before every live call; ~90 calls total):
1. Get a key: `NVIDIA_API_KEY` in `.env` (build.nvidia.com) and `HALO_PROFILE=nvidia-api`.
2. `uv run python spikes/list_models.py` (free) -> fill the four `UNSET` ids of `[profiles.nvidia-api]`; add prices if known.
3. Smoke test: `uv run python spikes/tool_calling_probe.py --tiers nano --n 1 --max-calls 2 --yes`; tune `structured_mode` / `extra_body` if needed.
4. Spike: `uv run python spikes/tool_calling_probe.py --yes --write` (60 calls) + embeddings check; record decisions.
5. Router golden set live (>=18/20; user reviews the 5 ambiguous labels first), then real `uv run halo "open VS Code"`.
6. Review (`reviewer`, `security-reviewer`), fix findings, push `feat/core-day2`, PR, CI green. Ask before push/merge.

## Next
- Day 3: HUD + character (`app.py`, pywebview, React reducer, `character/mood.py`, mascot, permission card). Needs no model.
- Then memory, coding session, security + voice, life skills, evals (see docs/PLAN.md).
- Re-run the live spike, router eval and cascade table on Token Factory when its key arrives; only those numbers are published.

## Known issues
- Nothing has run against a real model yet; the Windows `code` launch has never been exercised for real.
- Approved launch of a non-allowlisted app (e.g. Spotify) is not built: `app.open` returns `needs_approval` and the run ends in `error`.
  Needs a safe launch path (a model-supplied name must never reach a Windows shell).
- Server rejects the `null` Origin (a `file://` page); revisit when the HUD loading method is chosen.
- Voice accuracy is weak on live mic input; `sherpa-onnx` transducer variant fails to load (see `spikes/RESULTS.md`).
- `tests/fixtures/demo_repo` is gitignored (nested .git); regenerate per `spikes/claude_worker_probe.py`.
- Todo from Day 0: `~/HaloVault` not created/confirmed; Obsidian not confirmed installed.

## How to run
- `uv sync --all-extras` · tests `uv run pytest -m "not live" -q` · `uv run ruff check .` · `uv run pyright`
- CLI: `uv run halo "open VS Code"` (needs a key in `.env`; without one it explains what to set)
- API: `uv run python -m halo.api.server` (127.0.0.1:8765)
- Config: defaults in `src/halo/config.default.toml`; override with `~/.halo/config.toml` or `$HALO_CONFIG`.
