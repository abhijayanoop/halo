# Progress
_Last updated: 2026-10-12. Day numbers are the user's: Day 1 = Oct 10 (scaffold, contracts, spikes), Day 2 = Oct 11 (core brain, PLAN.md "Day 1"), Day 3 = HUD and character (PLAN.md "Day 2")._

## Done
- Day 1: scaffold, frozen contracts + schema export, CI, spikes for ASR, pywebview and claude-agent-sdk (`spikes/RESULTS.md`).
- Day 2, built and tested (245 offline tests; PR #3 `feat/core-day2` merged to main):
  event bus + ULID events, flight recorder (`~/.halo/runs/*.jsonl`), skill registry + `chat` and `app.open`,
  config loader, model client (retry, backoff, ₹ cost, `privacy: local` guard) + Nano-to-Super cascade,
  state, router, planner, LangGraph graph with approval gate (interrupt/resume, survives restart),
  `HaloRunner`, FastAPI server (`/run`, `/approve`, `WS /events`, localhost-only), `halo` CLI, `open_halo()` wiring.

## In progress: Day 3 (HUD + character) on branch `feat/hud-day3`; Day 2 was verified live on the dev profile
Live on `nvidia-api` (Nemotron from NVIDIA's hosted API; Nano stand-in = `nemotron-3.5-lightning-30b-a3b`, Super/Ultra/Omni = Nemotron 3 ids):
- Tool-calling + JSON-schema spike, 60 calls: 100% valid and correct on all three tiers (10 cases per kind per tier, small sample).
- Router golden set: passed (>=18/20; the exact score was not printed, ~160 s for 20 requests).
- Real `uv run halo "open VS Code"`: exit 0 in 8 s, VS Code launched, 11 events recorded and parsed back with 0 validation errors.
Reviews done (independent `reviewer` + `security-reviewer`); fixed: model-chosen risk, concurrent /approve, Origin scope, weak privacy matching,
provider text in `run.failed`, config read on the event loop. Remaining before Day 3:
1. (Done) PR #3 merged.
2. Latency: ~2-8 s per Nano call because the models think by default. Try `extra_body` to turn reasoning off (a few calls).
3. Print the exact router score (make the live test report hits); re-run everything on Token Factory when its key arrives.

## Day 3 stages (branch `feat/hud-day3`, built and tested offline)
Done: approval_id contract + approved launch of unlisted apps + API token + /events cleanup fix; `character/mood.py` + `MoodDirector` + `lines.py`;
UI scaffold, reducer, connection, API client; `app.py` shell; Rough.js mascot, bar, panel, permission card, `/moods`; review fixes from an independent reviewer,
a security reviewer and a visual reviewer. 498 Python and 91 UI tests pass; ruff, pyright, tsc and the UI build are clean.
Demo app is Notepad, not Spotify (not installed here). The "done when" loop is covered by `tests/api/test_demo_loop.py` (scripted model, real server, bus and mood director).
NOT yet done: the real window has never been opened (see Known issues), and nothing has been run against a live model today.

## Next
- First: install pywebview and run the real window once (see Known issues), then open the PR for `feat/hud-day3` (ask before pushing).
- Then memory, coding session, security + voice, life skills, evals (see docs/PLAN.md).
- Re-run the live spike, router eval and cascade table on Token Factory when its key arrives; only those numbers are published.

## Known issues
- **Not run for real yet:** `pywebview` is not in `pyproject.toml`/`uv.lock` and `halo-app` is not a script (the network was down for `uv add`). Run `uv add pywebview`,
  add `halo-app = "halo.app:entry"` under `[project.scripts]`, build the HUD (`cd ui && npm ci && npm run build`), then `uv run halo-app` and try "open Notepad".
  For the dev loop use `HALO_UI_URL=http://localhost:5173` with `npm run dev` (proxies to port 8765).
- Header Pause/Stop and the mic button are not built (no cancel path in the core yet). The Approvals, Memory, Ledger and History tabs are stubs.
- Event bus queues are unbounded (a stuck client could grow memory).
- `retry()` emits no `run.started`, so the mood engine keeps stale state during a retried run.
- A paused run restored from the checkpoint after a restart is not offered to a new HUD (the catch-up only knows approvals seen since this process started).
- "Always for this task" grants live in the SQLite checkpoint and `retry()` reuses them; `docs/CONTRACTS.md` says they are never persisted. Decide which is right.
- `~/.halo/api-token` is written with `chmod 600`, which does not change the ACL on Windows (it relies on the profile folder's default ACL).
- Mood events are not yet derived from sub-agent or Reader events (those modules do not exist), so Careful relies on a `payload.untrusted` flag on `tool.called`.
- The `privacy: local` guard is not wired yet: `open_halo` passes no `local_texts` (there is no vault yet). Wire it, failing closed, with memory (Day 4 of PLAN).
- Only Nemotron on NVIDIA's API has been exercised; Token Factory (the submission target) is untested until its key arrives.
- The HUD is served over http from the local server (same origin), so the `null` Origin (`file://`) is still rejected, on purpose.
- Voice accuracy is weak on live mic input; `sherpa-onnx` transducer variant fails to load (see `spikes/RESULTS.md`).
- `tests/fixtures/demo_repo` is gitignored (nested .git); regenerate per `spikes/claude_worker_probe.py`.
- Todo from Day 0: `~/HaloVault` not created/confirmed; Obsidian not confirmed installed.

## How to run
- `uv sync --all-extras` · tests `uv run pytest -m "not live" -q` · `uv run ruff check .` · `uv run pyright`
- CLI: `uv run halo "open VS Code"` (needs a key in `.env`; without one it explains what to set)
- API: `uv run python -m halo.api.server` (127.0.0.1:8765)
- Config: defaults in `src/halo/config.default.toml`; override with `~/.halo/config.toml` or `$HALO_CONFIG`.
