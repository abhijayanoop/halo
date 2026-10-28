# Progress
_Last updated: 2026-10-28. Day numbers are the user's: Day 1 = Oct 10 (scaffold, contracts, spikes), Day 2 = Oct 11 (core brain, PLAN.md "Day 1"), Day 3 = HUD, character and memory (PLAN.md "Day 2" and "Day 3"), Day 4 = the coding session (PLAN.md "Day 4")._

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
- Day 4, the coding session (PRs #6-#14 merged, 2026-10-27): `Tainted[T]` + a minimal `security/reader.py`; typed project notes with safe `last_stop` / session-log writes;
  `tools/repo_map.py` (HEAD-cached) and `tools/git_ops.py` (worktrees under `../.halo-worktrees`, local-only merge); the brief writer (`TaskBrief`, `test_cmd` always from the
  project note) and the Ultra reviewer (diff only as a fenced data block, verdict stays `Tainted`); `tools/claude_worker.py` (explicit tool list, PreToolUse hook + `can_use_tool`
  card, turn/cost/time caps; permission cards answered through the shared `/approve`); the `code.task` skill (brief card -> worktree -> worker -> Halo's own test run -> review ->
  result card with Merge / Iterate / Discard, answered through `POST /code/decision`); the HUD brief and result cards; `work.start` (no model call: where you stopped + up to three
  proposals from project notes and today's journal, clickable in the Now tab). `[coding]` limits in config: 150 rupees, 30 turns, 900 s, 600 s for the test run.
- **Live run, 2026-10-28 (Token Factory, real worker, driven over the API, merged on the user's go):** in `ai-eng-prep`, "add tests for token_count.py ... and fix the stray literal
  backslash-n" routed to `code.task`; the brief (edited down from 10 criteria to 5) was approved; Claude Code wrote `test_token_count.py` (8 tests) and the one-line fix in a
  worktree; Halo's own test run passed; Ultra said pass with no issues; the merge landed as two local commits on `main` (not pushed) and the worktree and branch were removed.
  Cost: Nano 0.008 + Super 0.113 + Ultra 0.233 + Claude Code 26.44 = 26.79 rupees. The worker's permission card was NOT seen on screen (no HUD was attached): it timed out and was
  denied after 5 minutes, and the worker finished without running tests itself.
- **Live HUD run, 2026-10-28 (`uv run halo-app`, the user clicked everything):** "add one-line docstrings to count_words, count_tokens and analyze_text ... remove the stray
  semicolon" in `ai-eng-prep`: the brief card (8 criteria) was approved 9 s after it appeared; the worker made five tool calls (Read, Bash x3, Edit) and finished at 14.39 rupees;
  Halo's own test run passed; Ultra said pass; the user clicked Merge on the result card and it landed as `ca79294` (+ a save commit) on the user's local `main`, touching only
  `token_count.py` (3 docstrings, the `;` removed). Total 14.69 rupees. The user reported that it works. **No worker permission card appeared** (Claude Code ran `git log` and
  the test command without asking), so that card has still only been seen as an event and in tests, not clicked on screen. Whether Enter on the result card does nothing was not
  separately checked.
- **Router golden set re-run after the `code.task` description changed (2026-10-28, Token Factory, live Nano):** 19/20 (the test's bar is 18); latency mean 1.18 s, max 2.15 s per
  route; all 3 `code.task` cases routed correctly. One miss: "what's the difference between a mutex and a semaphore?" (expected `chat`) went to `code.task`. Not attributed: it is
  one run of a non-deterministic model, and the earlier 20/20 (mean 1.7 s, max 10.5 s) used the old wording, so whether the new wording caused it is unknown (an A/B with the old
  description would tell). Cost was not measured: the run's script counted cost events, and routing without a run id emits none.
- Tests: 905 Python (`-m "not live"`), 200 UI; ruff, pyright, tsc and the UI build are clean.

## Next
- See a worker permission card on screen once (ask the worker for something off the allowlist, such as a file write outside the worktree or `git fetch`), and check that Enter
  on the result card does nothing.
- Done: Claude Code's `PowerShell` tool is treated like `Bash` in the tool policy (PR #15).
- Then PLAN Day 5, security + voice (the real Reader, policy engine, egress ledger, `web.read`), life skills, evals (the cascade table is a Day 7 item), see docs/PLAN.md.
- Day 3 live check (2026-10-27) passed: chat, recall with `obsidian://` links, the vault watcher, and the Notepad permission card.

## Known issues
- **Not built:** Pause (a model call in flight has no clean pause point), the mic button (voice is PLAN Day 5), the Approvals, Ledger and History tabs (stubs),
  the hidden-when-idle bar (dropped), poke/dizzy/file-swallow reactions (they would put mood in React or need a new event path).
- **Memory gaps:** keyword search only (the one embedding model on Token Factory, Qwen3-Embedding-8B, is not Nemotron, so vector search is skipped for now); a question can
  miss a fact worded differently ("what do I use for work?" ranks the Windows line first); duplicates are found by word overlap; a contradicting fact is not marked
  superseded; a proposal cannot be edited before approving; extraction is opt-in (`HALO_MEMORY_EXTRACT=1`).
- Thinking is off on the nvidia-api dev profile for every tier (planning quality on Super/Ultra unmeasured there); on Token Factory it is on.
- Omni tier is unset on Token Factory (no Nano Omni listed); nothing uses it yet.
- Token Factory prices in the config are unverified third-party estimates (see the warning in config.default.toml); confirm them in the Nebius console before publishing any cost figure.
- A recorded event is dropped if a subscriber falls 1000 events behind (bounded queue); the flight recorder drains far faster, but it is a possible gap.
- `retry()` after a Stop is not possible (the run is finished), and a stopped run's checkpoint is left as it was.
- `~/.halo/api-token` is written with `chmod 600`, which does not change the ACL on Windows (it relies on the profile folder's default ACL).
- Mood events are not yet derived from sub-agent or Reader events (those modules do not exist), so Careful relies on a `payload.untrusted` flag on `tool.called`.
- The HUD is served over http from the local server (same origin), so the `null` Origin (`file://`) is still rejected, on purpose.
- The window was checked in the real window with a real click; not yet on a second monitor, other display scales, or by dragging the bar.
- The old folder `C:\Users\abhij\HaloVault` (made by an earlier run) is unused; delete it when convenient.
- Voice accuracy is weak on live mic input; `sherpa-onnx` transducer variant fails to load (see `spikes/RESULTS.md`).
- `tests/fixtures/demo_repo` is gitignored (nested .git); regenerate per `spikes/claude_worker_probe.py`.
- **Coding session gaps:** one Claude Code turn can cost about 13 rupees and a small task cost 26 (the cap is 150); the brief card, the worker's permission card and the result card
  wait 5 / 5 / 30 minutes before a denial or "kept"; a Halo restart mid-session leaves the worktree on disk with no way back to it; "Open in VS Code" on the result card is not built;
  the first `uv run` test in a fresh worktree builds a new virtualenv; the brief writer can produce vague criteria (edit them on the card).
- `python -m halo.api.server` does not serve the HUD page (404 at `/`), so cards cannot be clicked from it; a second launch while one is running overwrites `~/.halo/api-token`,
  so the running server's token no longer matches. `/stop` and `/memory/*` are not in the token-protected set (only `/run`, `/approve`, `/code/decision` and `/events` are).
- Symlink protections (a link out of the vault is not followed) are tested but skipped on this Windows account; they run on Linux CI.
- `load_config()` does not read `.env`; the entry points (`halo-app`, the API server, the CLI) call `load_env()` first. A script that builds a model client must call `load_env()`
  too, or it will report the key as missing even when `.env` has it. The live golden-set test runs under the global 30 s timeout and its 20 calls can exceed it (it did once); pass `--timeout=300` or use a script.
- The router can send a general programming question to `code.task` (1 miss in the 20-case golden set); re-run the set after any change to a skill description.
- The `NVIDIA_API_KEY` value was pasted into a chat on 2026-10-28; regenerate it if it was a real key.

## How to run
- `uv sync --all-extras` · tests `uv run pytest -m "not live" -q` · `uv run ruff check .` · `uv run pyright`
- App: `cd ui && npm ci && npm run build`, then `uv run halo-app` (`HALO_DEMO=1 uv run halo-app` replays the tour; dev: `HALO_UI_URL=http://localhost:5173` with `npm run dev`)
- CLI: `uv run halo "open VS Code"` (needs a key in `.env`; without one it explains what to set)
- API: `uv run python -m halo.api.server` (127.0.0.1:8765)
- Config: defaults in `src/halo/config.default.toml`; override sections in `~/.halo/config.toml`, or use `$HALO_CONFIG` for a standalone file; `HALO_PROFILE=token-factory` or `nvidia-api`.
