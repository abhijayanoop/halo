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
Blocked on a live endpoint. Plan (tests first, ask before any live call; live calls capped at ~90 total):
1. Provider profiles: config `profile` (`nvidia-api` dev, `token-factory` final), per-profile base URL / key var / model ids;
   structured-output mode (`json_schema` | `json_object` | `prompt`); strip `<think>` / read `reasoning_content`.
2. Spike harness `spikes/tool_calling_probe.py` with a hard call cap; dry-run against the fake transport first.
3. LIVE (needs a key): list models, 3-call smoke test, tool-calling + JSON-schema spike (Nano, Super, Ultra),
   record numbers + decisions in `spikes/RESULTS.md`, embeddings check.
4. LIVE: router golden set (needs ≥18/20; user reviews the 5 ambiguous labels first), then real `uv run halo "open VS Code"`.
5. Review (`reviewer`, `security-reviewer`), fix findings, push `feat/core-day2`, PR, CI green. Ask before push/merge.

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
