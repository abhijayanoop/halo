# Halo — Product Spec (v0.1)

Source of truth for *what* Halo does. *How* it's built lives in `docs/ARCHITECTURE.md`; the day-by-day build order lives in `docs/PLAN.md`. This spec is written from those two documents plus an interview on the ambiguous points (scope, risk tiers, egress boundary, failure behaviour, Windows specifics); see `docs/DECISIONS.md` for the choices made and why.

## Goals, in order

1. **A tool used every day.** Coding work sessions, memory, research and expenses must be dependable enough to use without the hackathon as a reason.
2. **Win the Personal AI track.** Signature features: the character-driven glass-box HUD, memory with per-fact provenance, a trust boundary untrusted content can't cross, and Nemotron acting as tech lead over Claude Code.
3. **Prove AI-engineering depth.** Real numbers in the README: golden-task success rate, prompt-injection attack success with and without defences, cost and latency per Nemotron model.

## Users

- **Primary: the builder, as daily driver.** A solo developer on Windows running several coding projects, who wants a visible, interruptible agent rather than a black box — not a hypothetical persona, literally whoever is running Halo on their own machine and vault.
- **Secondary: a hackathon judge or new user.** Runs the demo vault/persona bundled with the release, provided a Token Factory key (own or the rate-limited demo key), and should reach a working first command in under 5 minutes.

## Features (v0.1)

v0.1 is the full Day 1–6 build: core brain, HUD/character, memory, the coding work session, security, voice, trip planning, expenses, launcher, and scheduled briefs. The plan's "cut list" (receipts, TTS, Google Calendar MCP, the 19:00 check, the morning brief, in that order) is a time-box fallback if a day slips — not a pre-emptive reduction of this spec. If a cut is taken, it's recorded in `docs/DECISIONS.md` and the feature below is marked accordingly.

### F1 — Core brain (router → planner → executor, event bus, recorder)

- `uv run halo "open VS Code"` opens VS Code; the CLI prints `run.started` → `step.*` → `run.finished` live via `rich`.
- The same events are appended verbatim to `~/.halo/runs/YYYY-MM-DD.jsonl` and parse back into `HaloEvent` with zero validation errors.
- `evals/router_golden.yaml` (20 utterances, 5 ambiguous) scores **≥18/20** on live Nemotron Nano.
- Escalation rule: a Nano call with confidence `<0.7`, or a Pydantic validation failure after one retry, escalates to Super. Every escalation is logged with its cost and latency via `cost.updated`.
- A test fails if `schemas/` (JSON Schema exports of the contracts) is out of date relative to `halo/core/contracts.py`.

### F2 — HUD and character

- Collapsed bar renders at 260×44px, top centre. A mood holds for **≥700ms** even under back-to-back tool calls (no flicker).
- Demo case: typing "open Spotify" (not allowlisted) drives mood Thinking → Asking; the permission card (380×140px) shows the exact action and risk level; Enter allows, Esc denies; after allow, Spotify opens and mood goes Delighted for 2s, then Idle.
- The `/moods` dev page renders all 13 moods; the `ui-critic` subagent's screenshot comparison against the mood table in `docs/ARCHITECTURE.md` finds no mismatched accessory or ring colour.
- Status lines are ≤7 words, present tense, specific nouns, no emoji/exclamation marks in errors. The template fallback fires (and is tested) when Nano exceeds 400ms or fails schema validation.

### F3 — Memory

- After an app restart, "what did I pick for the HUD window?" is answered from a vault note, with an `obsidian://` link and visible source/trust.
- Deleting that bullet line in Obsidian causes the next recall (after one `watchdog` re-index cycle, 300ms debounce) to say it doesn't know.
- RRF retrieval is order-independent: swapping the two input rank lists doesn't change the fused result (property test).
- `assemble_context(budget_tokens=1500)` never includes an item from a `privacy: local` note — verified with a Hypothesis property test over generated notes, not just examples.
- A `memory.proposed` candidate with cosine similarity ≥0.9 to an existing item is suppressed as a duplicate; a contradicted fact is marked superseded, not deleted.

### F4 — Coding work session

- On a real repo: "add rate limiting to the webhook endpoint" → Super writes a `TaskBrief` (editable in the approval card) → approve → a worktree is created at `../.halo-worktrees/<repo>/<slug>` on branch `halo/<slug>` → Claude Code's edits appear live in the agent tree (`tool.called`/`tool.result`/`agent.spawned`) → Halo runs `test_cmd` itself in the worktree → Ultra returns a `Review` (`pass`/`concerns`) graded against the brief's acceptance criteria → Open in VS Code / Merge / Iterate / Discard all work from the result card.
- **Failure mode — worker or test command hangs:** the process tree is killed at the timeout, the `Review` is marked `concerns: test command timed out`, the worktree and partial diff are preserved for inspection or `Iterate`, and the change is never auto-merged.
- **Failure mode — model outage:** if a model call fails after retry and escalation (e.g. Token Factory down or rate-limited), the run ends with `run.failed` and a plain-language reason, mood goes to Confused, the LangGraph checkpoint is left intact so the run can resume later, and no partially-applied file, memory or expense write is left behind.
- "let's get to work" (`work.start`) reads project notes, `last_stop` and today's journal, and proposes 1–3 tasks within 1.5s of the phrase being heard or typed.
- `CodingWorker` is a Protocol; only the Claude Code implementation ships in v0.1 (see Constraints).

### F5 — Security

- `evals/injection_suite/` has **≥15** fixture attacks (hidden instructions in a web page, a README, email text, a poisoned memory). For every attack: no blocked tool actually runs, a `policy.blocked` event fires, the HUD shows Guarding mood with a red banner naming the reason, and the user's original task still completes wherever it doesn't require the blocked step.
- A test asserts the model client **raises** if any text from a `privacy: local` note appears in a cloud prompt payload — this is a hard failure, not a log line.
- High-risk tools (delete files, send messages, spend money, `git push`/`merge`) cannot be set to "always allow", enforced in code and covered by a test, not just documented.
- "Always for this task" approvals are **session-scoped**: granted in memory for the current run/session, gone on restart. Nothing escalates to a persistent always-allow in v0.1.
- `evals/report.md` reports attack success rate with defences off vs on, plus utility-under-attack (did the legitimate task still finish) for the same cases.

### F6 — Voice

- Holding the hotkey (configurable in `config.toml`/`Profile.md`, **default Ctrl+Space**) starts `voice.listening`; VAD end-of-speech finalizes `voice.heard`. Target latency from PLAN Day 5 spikes is under 1s.
- Onboarding attempts to register the hotkey; if registration fails (already bound by another app or an IME), onboarding says so and lets you rebind rather than Halo silently not responding.
- "let's get to work" / "let's get started" route directly to `work.start`, bypassing the general router.
- ASR is testable without hardware: a `--wav` input path and a `FakeMic` fixture exist so CI covers end-of-speech detection.

### F7 — Trip planning

- "plan a 4-day Goa trip in December under budget" fans out five sub-agents (stay, transport, places, season/weather, budget) via LangGraph `Send`, each capped at 6 tool calls; the HUD shows one orbiting mini-halo per running helper.
- The budget helper calls only `finance.monthly_surplus()` locally — never a network tool. The egress ledger for this run shows zero salary/transaction bytes sent, only the surplus figure.
- `Trips/<slug>.md` contains only facts carrying a source URL from a sub-agent; an uncited claim is dropped before synthesis (tested with a fixture result containing one uncited claim).
- Preferences noticed during research (e.g. "prefers beach stays") surface as `memory.proposed`, never auto-saved.
- Calendar hold uses a Google Calendar MCP server behind a medium-risk approval; if OAuth setup exceeds roughly an hour, the fallback is writing and opening an `.ics` file instead — either path satisfies this feature.

### F8 — Expenses

- "spent 450 on lunch at Cafe X" → a parsed `Expense` row in SQLite, mirrored to `Finance/YYYY-MM.md` (`privacy: local`); a 10-case parse test suite passes.
- "how much on food this month?" → Nano parses an `ExpenseQuery`; **SQL computes the total, never the model**; an 8-case query test suite asserts exact totals against SQL ground truth.
- Crossing a category budget (from the Finance note's frontmatter) shows a warning in the status line on the next related log or query.
- A receipt photo dropped on the HUD is extracted by Nemotron Nano Omni into an `Expense` with a confidence score; the permission card states explicitly that the image is being sent to Nemotron before the call happens.

### F9 — Launcher and scheduling

- `app.open` resolves aliases and the allowlist from `Profile.md`. An allowlisted app opens without asking (low risk); a non-allowlisted one always asks first (medium risk).
- A 09:00 morning brief (APScheduler, or triggered by hand) surfaces today's calendar, each project's `last_stop`, budget status and one suggested first task.
- A 19:00 end-of-day check (or triggered by hand) asks where you stopped and writes the answer to `last_stop`.

## Non-goals (v0.1)

- **macOS as a first-class target.** Windows is tested and shipped; a macOS build is attempted in CI but labelled untested — Mac users run from source.
- **Code-signing the installer.** The build is unsigned; Windows SmartScreen will warn on first run. This is a documented known limitation in the README ("More info → Run anyway"), not something fixed this week.
- **Swapping the coding worker.** The `CodingWorker` protocol exists for future portability, but only the Claude Code implementation ships.
- **Multi-user, team, or cloud-synced vault features.** The vault is single-user and local; there is no sync, sharing or multi-tenant story.
- **Autonomous unattended operation.** Halo never runs a medium- or high-risk action without an approval in the loop; there is no "run overnight unattended" mode.
- **An open-ended, un-sandboxed agent.** v0.1 ships a fixed skill registry (`chat`, `app.open`, `code.task`, `trip.plan`, `expense.log`, `expense.query`, `memory.remember`, `memory.recall`, `memory.forget`, `work.start`), not a general computer-use agent.
- **Persistent "always allow" grants.** Deferred; v0.1's approval grants are session-scoped only (see F5).

## Constraints

- **Nemotron-only for Halo's own reasoning.** Every router, planner, judge, Reader, memory-extraction, mood/status-line call goes through `halo/models/client.py` to Nemotron on Nebius Token Factory, and only that. **Declared exception:** the Day 4 coding worker uses `claude-agent-sdk`, which calls Anthropic's Claude API to perform code edits — this is a separate, intentional dependency of the `CodingWorker` tool, not of Halo's own cognition, and it is called out explicitly here and in the README's model table rather than hidden inside "Nemotron only."
- Python 3.12, managed with `uv`. Code must also run on macOS (`pathlib` only, no shell-specific syntax in Python) even though macOS isn't a tested target.
- Windows first; the dev shell is Git Bash. The global hotkey is read from config, defaults to Ctrl+Space, and is rebindable if it collides with an IME or another app's binding.
- The vault is a local Obsidian folder the user owns. Notes tagged `privacy: local` never enter a cloud prompt — enforced by a raising check in the model client, not just a convention.
- Per-run and per-day ₹ cost caps come from `config.toml`, enforced via the egress ledger.
- High-risk tools (delete, send, spend, git push/merge) can never be configured to "always allow"; "always for this task" grants never outlive the session.
- All inter-component communication is one typed `HaloEvent`; the UI derives all of its state from the event stream and invents none of its own.

## Risk tiers (for the approval policy table)

| Tier | Definition | Examples |
| --- | --- | --- |
| **Low** | Read-only or trivially reversible; runs without asking | `chat`, `memory.recall`, `repo_map` generation, `code_task` explain mode, an allowlisted `app.open` |
| **Medium** | Writes something, but it's easy to undo or scoped to an isolated place; asks once, may be set to "always for this task" (session-scoped) | Non-allowlisted `app.open`, `memory.remember`, a calendar hold, `code_task` plan mode, writing a vault note, `code_task` implement (file edits happen only in an isolated worktree, never on `main`) |
| **High** | Irreversible, external, or financial; always asks, can never be set to "always allow" | Deleting files, sending messages/emails, any expense write, `git push`/`merge` to `main`, running arbitrary/unapproved shell |

## Failure behaviour (summary)

| Situation | Behaviour |
| --- | --- |
| Model call fails after retry + escalation (outage, rate limit) | `run.failed` with a plain reason; mood → Confused; checkpoint preserved so the run can resume; no partial file/memory/expense writes left behind |
| Coding worker or its test command hangs past timeout | Process tree killed; `Review` = `concerns: test command timed out`; worktree and diff kept for `Iterate`/inspection; never auto-merged |
| Policy engine blocks a tool call (injection, risk) | That step is blocked and logged (`policy.blocked`); Guarding mood + red banner with the reason; the rest of the run continues and finishes if it doesn't depend on the blocked step, otherwise it ends with a clear explanation — never a silent partial success |
| Hotkey registration fails (already bound) | Reported during onboarding with an offer to rebind, not a silent no-op |
| Mic/ASR error | Falls back to typing; Halo never crashes or blocks on a voice failure |

## End-to-end demo script

A single walkthrough exercising every v0.1 feature, in the order a real session would hit them.

1. **Cold start (judges/new users only).** Run the installer, pick the demo vault and the demo key, test the mic. Speech model downloads with a progress bar. Target: under 5 minutes to the first successful command.
2. **Wake.** Ctrl+Space, say or type "let's get to work." Halo wakes from Asleep, greets you with where you stopped (`last_stop`), and proposes 1–3 tasks.
3. **Coding work session.** Pick a task; approve the `TaskBrief`; watch Claude Code edit in the agent tree inside an isolated worktree; Halo runs the tests itself; Ultra's review appears; Merge.
4. **Trip planning.** "Plan a 4-day Goa trip in December under budget." Five mini-halos orbit while sub-agents research in parallel; the sourced note lands in `Trips/`; open the Ledger tab and confirm only the surplus figure left the laptop.
5. **Expenses.** "Spent 450 on lunch at Cafe X" is logged; "how much on food this month?" answers with a SQL-computed total.
6. **Security.** Ask Halo to summarise a fixture page with a hidden instruction. The Reader extracts only the legitimate fact; the hidden instruction's target action is blocked; Guarding mood, red banner, reason shown.
7. **Memory and forgetting.** "What did I pick for the HUD window?" answers with a source link. Delete that line in Obsidian. Ask again — Halo says it doesn't know.
8. **Shutdown.** Leave Halo idle past the timeout; it returns to Asleep.

Each step above maps to a "Done when" check already defined in the Features section, so the demo script is not a separate set of claims — it's the features, run in sequence.
