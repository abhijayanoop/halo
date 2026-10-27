# Progress
_Last updated: 2026-10-27. Day numbers are the user's: Day 1 = Oct 10 (scaffold, contracts, spikes), Day 2 = Oct 11 (core brain, PLAN.md "Day 1"), Day 3 = HUD, character and memory (PLAN.md "Day 2" and "Day 3")._

## Done
- Day 1: scaffold, frozen contracts + schema export, CI, spikes for ASR, pywebview and claude-agent-sdk (`spikes/RESULTS.md`).
- Day 2 (PR #3, merged): event bus + ULID events, flight recorder (`~/.halo/runs/*.jsonl`), skill registry + `chat` and `app.open`, config loader,
  model client (retry, backoff, ₹ cost, `privacy: local` guard) + Nano-to-Super cascade, state, router, planner, LangGraph graph with approval gate
  (interrupt/resume, survives restart), `HaloRunner`, FastAPI server, `halo` CLI, `open_halo()` wiring.
- Day 3, HUD and character (PR #4 `feat/hud-day3`, open, UI approved by the user): mood engine + status lines, pywebview shell (`halo-app`), an opaque window cut to a rounded
  shape, permission card with Enter/Esc, API token. Flat dark design: a one-squircle mascot whose body colour is the mood (thin halo kept), corner badge, cursor-following eyes;
  bar with a progress line and a blinking activity light; risk-coloured card; two-column panel (rail + Now / Memory tabs); dark scrollbars; Stop button;
  the answer to a request and the failure reason shown in the Now tab; `HALO_DEMO=1` replays a scripted tour of all 13 moods.
- Day 3, core fixes: always-grants are session-only, `retry()` announces `run.started`, bounded event queues, paused runs restored after a restart reach a new HUD,
  quiet `/events` close, `POST /stop` and `HaloRunner.stop()`.
- Day 3, memory: Obsidian vault with FTS5 index + RRF, expiry, trust and a 1500-token budget, `memory.remember` / `recall` / `forget`, memory in the router and planner prompts,
  `privacy: local` text feeding the model guard, file watcher, proposed memories (opt-in) with Approve/Reject in the HUD.
  The vault is `C:\Users\abhij\Documents\main-folder\HaloVault` (set in `~/.halo/config.toml`, which now overrides the packaged defaults section by section). It holds `Profile.md`
  (7 facts from the user) and `Projects/halo.md` (10 facts read from the repo, plus the Day 4 frontmatter). Obsidian 1.14.4 is installed.
- Nebius Token Factory (the submission profile) is configured: base URL and the Nano, Super and Ultra ids read from the models endpoint (Omni unset, no Nano Omni listed).
  **Live, published numbers (2026-10-27):** tool-calling and JSON-schema spike 60/60 on all three tiers, median 1.0-1.2 s; router 20/20 on the golden set with the shipped config
  (thinking on), mean 1.7 s, max 10.5 s (thinking off: 18/20 at 0.8 s). See `spikes/RESULTS.md`.
- Dev profile (nvidia-api, dev numbers only): thinking off cut a Nano call from about 4 s to under 1 s there.
- Tests: 681 Python (`-m "not live"`), 157 UI; ruff, pyright, tsc and the UI build are clean.

## Next
- You: set `HALO_PROFILE=token-factory` in `.env` (it still says `nvidia-api`, which overrides the config), open `HaloVault` in Obsidian once ("Open folder as vault"), and add the
  Token Factory prices from the console (USD per million tokens) so ₹ costs are real. Then I run the live Day 3 "done when": restart, ask "what did I pick for the HUD window?",
  get the answer with a link, delete the line in Obsidian, ask again, get "I don't know"; and a live "who are you" and the live Notepad approval.
- Merge PR #4 when you say so.
- Then Day 4, the coding session (plan awaiting approval), security + voice, life skills, evals (the cascade table is a Day 7 item), see docs/PLAN.md.

## Known issues
- **Not built:** Pause (a model call in flight has no clean pause point), the mic button (voice is PLAN Day 5), the Approvals, Ledger and History tabs (stubs),
  the hidden-when-idle bar (dropped), poke/dizzy/file-swallow reactions (they would put mood in React or need a new event path).
- **Memory gaps:** keyword search only (the one embedding model on Token Factory, Qwen3-Embedding-8B, is not Nemotron, so vector search is skipped for now); a question can
  miss a fact worded differently ("what do I use for work?" ranks the Windows line first); duplicates are found by word overlap; a contradicting fact is not marked
  superseded; a proposal cannot be edited before approving; extraction is opt-in (`HALO_MEMORY_EXTRACT=1`).
- Thinking is off on the nvidia-api dev profile for every tier (planning quality on Super/Ultra unmeasured there); on Token Factory it is on.
- Omni tier is unset on Token Factory (no Nano Omni listed); nothing uses it yet.
- Token Factory prices are not in the config, so costs show as not known.
- A recorded event is dropped if a subscriber falls 1000 events behind (bounded queue); the flight recorder drains far faster, but it is a possible gap.
- `retry()` after a Stop is not possible (the run is finished), and a stopped run's checkpoint is left as it was.
- `~/.halo/api-token` is written with `chmod 600`, which does not change the ACL on Windows (it relies on the profile folder's default ACL).
- Mood events are not yet derived from sub-agent or Reader events (those modules do not exist), so Careful relies on a `payload.untrusted` flag on `tool.called`.
- The HUD is served over http from the local server (same origin), so the `null` Origin (`file://`) is still rejected, on purpose.
- The window was checked in the real window with a real click; not yet on a second monitor, other display scales, or by dragging the bar.
- The old folder `C:\Users\abhij\HaloVault` (made by an earlier run) is unused; delete it when convenient.
- Voice accuracy is weak on live mic input; `sherpa-onnx` transducer variant fails to load (see `spikes/RESULTS.md`).
- `tests/fixtures/demo_repo` is gitignored (nested .git); regenerate per `spikes/claude_worker_probe.py`.

## How to run
- `uv sync --all-extras` · tests `uv run pytest -m "not live" -q` · `uv run ruff check .` · `uv run pyright`
- App: `cd ui && npm ci && npm run build`, then `uv run halo-app` (`HALO_DEMO=1 uv run halo-app` replays the tour; dev: `HALO_UI_URL=http://localhost:5173` with `npm run dev`)
- CLI: `uv run halo "open VS Code"` (needs a key in `.env`; without one it explains what to set)
- API: `uv run python -m halo.api.server` (127.0.0.1:8765)
- Config: defaults in `src/halo/config.default.toml`; override sections in `~/.halo/config.toml`, or use `$HALO_CONFIG` for a standalone file; `HALO_PROFILE=token-factory` or `nvidia-api`.
