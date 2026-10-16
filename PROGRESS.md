# Progress
_Last updated: 2026-10-17. Day numbers are the user's: Day 1 = Oct 10 (scaffold, contracts, spikes), Day 2 = Oct 11 (core brain, PLAN.md "Day 1"), Day 3 = HUD, character and memory (PLAN.md "Day 2" and "Day 3")._

## Done
- Day 1: scaffold, frozen contracts + schema export, CI, spikes for ASR, pywebview and claude-agent-sdk (`spikes/RESULTS.md`).
- Day 2 (PR #3 `feat/core-day2`, merged): event bus + ULID events, flight recorder (`~/.halo/runs/*.jsonl`), skill registry + `chat` and `app.open`,
  config loader, model client (retry, backoff, ₹ cost, `privacy: local` guard) + Nano-to-Super cascade, state, router, planner,
  LangGraph graph with approval gate (interrupt/resume, survives restart), `HaloRunner`, FastAPI server, `halo` CLI, `open_halo()` wiring.
- Day 3, HUD and character (branch `feat/hud-day3`): mood engine + status lines, pywebview shell (`halo-app`), the permission card and Enter/Esc,
  `approval_id`, API token, security fixes from three reviews. Then the redesign:
  smooth vector mascot (no Rough.js) with glossy cursor-following eyes, a distinct face per mood and a glowing ring; glass bar tinted by mood with a progress bar;
  risk-coloured permission card with key caps; Now tab with step status dots, durations and the exact memories used; Stop button; Memory tab.
- Day 3, core fixes: always-grants are session-only (not in the checkpoint), `retry()` announces `run.started`, bounded event queues,
  paused runs restored after a restart reach a new HUD, `/events` no longer raises when the socket is already gone, `POST /stop` and `HaloRunner.stop()`.
- Day 3, memory (PLAN "Day 3"): Obsidian vault (`~/HaloVault`, created from a template), FTS5 index with RRF, expiry, trust and a 1500-token budget,
  `memory.remember` / `recall` / `forget`, memory in the router and planner prompts, `privacy: local` text feeding the model guard, file watcher,
  proposed memories (opt-in extraction, inbox note, `/memory/approve` and `/memory/reject`), HUD Memory tab.
- Live on the `nvidia-api` dev profile (dev numbers only; only Token Factory runs are published): Nano router call about 4 s with thinking on, under 1 s with
  `enable_thinking=false` (now set on that profile), router 20/20 on the golden set with it off.
- Tests today: 658 Python (`-m "not live"`), 125 UI; ruff, pyright, tsc and the UI build are clean. The real window starts and stays up.

## Next
- You: look at the real window (always-on-top, resize, Enter/Esc on the card, the new look) and approve the UI, then I open the PR for `feat/hud-day3`.
- Then the coding session, security + voice, life skills, evals (see docs/PLAN.md).
- Re-run the live spike, router eval and cascade table on Token Factory when its key arrives; only those numbers are published.

## Known issues
- **Not built:** Pause (a model call in flight has no clean pause point), the mic button (voice is PLAN Day 5), the Approvals, Ledger and History tabs (stubs),
  the hidden-when-idle bar (dropped, see DECISIONS), poke/dizzy/file-swallow reactions (they would put mood in React or need a new event path).
- **Memory gaps:** keyword search only (no embedding model is configured, so no vector search); duplicates are found by word overlap, not cosine;
  a contradicting fact is not marked superseded; a proposal cannot be edited before approving; extraction is opt-in (`HALO_MEMORY_EXTRACT=1`).
  `~/HaloVault` holds only the template: add your `Profile.md` facts and project notes (PLAN Day 3 item 9). Obsidian is still unconfirmed on this machine.
- **Reasoning off applies to every tier** on the dev profile, so planning quality on Super/Ultra is unmeasured; re-check on Token Factory.
- A recorded event is dropped if a subscriber falls 1000 events behind (bounded queue); the flight recorder drains far faster, but it is a possible gap.
- `retry()` after a Stop is not possible (the run is finished), and a stopped run's checkpoint is left as it was.
- `~/.halo/api-token` is written with `chmod 600`, which does not change the ACL on Windows (it relies on the profile folder's default ACL).
- Mood events are not yet derived from sub-agent or Reader events (those modules do not exist), so Careful relies on a `payload.untrusted` flag on `tool.called`.
- Only Nemotron on NVIDIA's API has been exercised; Token Factory (the submission target) is untested until its key arrives.
- The HUD is served over http from the local server (same origin), so the `null` Origin (`file://`) is still rejected, on purpose.
- The window is now `transparent`; the pill's rounded corners and the glass blur have been checked in a browser, not yet by eye in the real window.
- Voice accuracy is weak on live mic input; `sherpa-onnx` transducer variant fails to load (see `spikes/RESULTS.md`).
- `tests/fixtures/demo_repo` is gitignored (nested .git); regenerate per `spikes/claude_worker_probe.py`.

## How to run
- `uv sync --all-extras` · tests `uv run pytest -m "not live" -q` · `uv run ruff check .` · `uv run pyright`
- App: `cd ui && npm ci && npm run build`, then `uv run halo-app` (dev: `HALO_UI_URL=http://localhost:5173` with `npm run dev`)
- CLI: `uv run halo "open VS Code"` (needs a key in `.env`; without one it explains what to set)
- API: `uv run python -m halo.api.server` (127.0.0.1:8765)
- Config: defaults in `src/halo/config.default.toml`; override with `~/.halo/config.toml` or `$HALO_CONFIG`; `HALO_PROFILE=nvidia-api` for the dev profile.
