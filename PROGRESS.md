# Progress
_Last updated: 2026-10-12. Day numbers are the user's: Day 1 = Oct 10 (scaffold, contracts, spikes), Day 2 = Oct 11 (core brain, PLAN.md "Day 1"), Day 3 = HUD and character (PLAN.md "Day 2")._

## Done
- Day 1: scaffold, frozen contracts + schema export, CI, spikes for ASR, pywebview and claude-agent-sdk (`spikes/RESULTS.md`).
- Day 2, built and tested offline (201 tests, branch `feat/core-day2`, 6 commits, not yet pushed):
  event bus + ULID events, flight recorder (`~/.halo/runs/*.jsonl`), skill registry + `chat` and `app.open`,
  config loader, model client (retry, backoff, ₹ cost, `privacy: local` guard) + Nano-to-Super cascade,
  state, router, planner, LangGraph graph with approval gate (interrupt/resume, survives restart),
  `HaloRunner`, FastAPI server (`/run`, `/approve`, `WS /events`, localhost-only), `halo` CLI, `open_halo()` wiring.

## In progress: Day 2 verified live on the dev profile; review, push, then Day 3
Live on `nvidia-api` (Nemotron from NVIDIA's hosted API; Nano stand-in = `nemotron-3.5-lightning-30b-a3b`, Super/Ultra/Omni = Nemotron 3 ids):
- Tool-calling + JSON-schema spike, 60 calls: 100% valid and correct on all three tiers (10 cases per kind per tier, small sample).
- Router golden set: passed (>=18/20; the exact score was not printed, ~160 s for 20 requests).
- Real `uv run halo "open VS Code"`: exit 0 in 8 s, VS Code launched, 11 events recorded and parsed back with 0 validation errors.
Remaining:
1. Reviews running (`reviewer`, `security-reviewer`); fix findings.
2. Push `feat/core-day2`, open PR, CI green. Ask before push and before merge.
3. Latency: ~2-8 s per Nano call because the models think by default. Try `extra_body` to turn reasoning off (cheap test, a few calls).
4. Embeddings: `nvidia/nemotron-3-embed-1b` exists on the NVIDIA API; availability on Token Factory unknown. Decide later (else local `fastembed`).
5. Print the exact router score (make the live test report hits) and re-run on Token Factory when its key arrives.

## Next
- Day 3: HUD + character (`app.py`, pywebview, React reducer, `character/mood.py`, mascot, permission card). Needs no model.
- Then memory, coding session, security + voice, life skills, evals (see docs/PLAN.md).
- Re-run the live spike, router eval and cascade table on Token Factory when its key arrives; only those numbers are published.

## Known issues
- Only Nemotron on NVIDIA's API has been exercised; Token Factory (the submission target) is untested until its key arrives.
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
