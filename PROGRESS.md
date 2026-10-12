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

## Day 3 stages
Done and committed on `feat/hud-day3`: 0 housekeeping · 1 approval_id contract, approved launch of unlisted apps, API token, /events cleanup fix · 2 `character/mood.py` + `MoodDirector` · 3 UI scaffold, reducer, connection, API client · 4 `app.py` (pywebview shell, guarded `js_api`, server thread, static UI) · 5 mascot, bar, panel, `/moods`.
In progress: 6 permission card + e2e (`PermissionCard` built and tested; still to wire into `App.tsx`) · then 7 `character/lines.py` · 8 polish + reviews + PR.
Demo app is Notepad, not Spotify (not installed here).

## Next
- Day 3: HUD + character (`app.py`, pywebview, React reducer, `character/mood.py`, mascot, permission card). Needs no model.
- Then memory, coding session, security + voice, life skills, evals (see docs/PLAN.md).
- Re-run the live spike, router eval and cascade table on Token Factory when its key arrives; only those numbers are published.

## Known issues
- Event bus queues are unbounded (a stuck client could grow memory). Bound them, dropping the slow subscriber, when it matters.
- `pywebview` is not yet in `pyproject.toml`/`uv.lock` and `halo-app` is not yet a script: the network was down for `uv add` (DNS). Run `uv add pywebview`, then add
  `halo-app = "halo.app:entry"` under `[project.scripts]`. `python -m halo.app` works once pywebview is installed. The window itself has not been run yet.
- Starting the app needs the HUD built: `cd ui && npm ci && npm run build` (or `HALO_UI_URL=http://localhost:5173` with `npm run dev`, which proxies to port 8765).
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
