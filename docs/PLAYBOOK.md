# Halo × Claude Code: the 8-day build playbook

**What this file is.** A complete, opinionated guide to building Halo with Claude Code in 8 days, from the first prompt to a tagged GitHub release. It covers the industry-standard workflow (spec → contracts → plan → test-first → verify → review → ship), how to set up Claude Code so it works *for* you, the exact prompts and sessions for each day, and how to keep everything reusable for future projects.

**What it is not.** It doesn't repeat *what* Halo is. That lives in the **Halo 8-Day Hackathon Build Plan** doc (architecture, character, moods, day goals). This playbook is *how* to build it with Claude Code. Keep both open.

**Dates.** The build runs **Day 1 = Sat Oct 10 → Day 8 = Sat Oct 17**, one day later than the original plan doc. Video and write-up run Oct 18–24, you submit on **Tue Oct 27**, and the hard deadline is Fri Oct 30, 10:30 PM IST.

**How to read it.**

- Part 1 (mental model) and Part 2 (setup) are read once, carefully, before Day 1.
- Part 3 (daily loop) and Part 4 (prompt playbook) are the reference you'll use every day.
- Part 5 is the day-by-day build.
- Parts 6–10 cover testing, CI/CD and release, troubleshooting, time budgeting, and the reusable kit.
- Appendix A holds every config file in full, ready to copy.

All Claude Code commands and settings here were checked against the official docs (code.claude.com) in October 2026. Claude Code updates often: if something behaves differently, run `/help` or check the docs page listed in Appendix C.

---

## Part 1 — How agentic coding actually works

### 1.1 The loop

Claude Code isn't autocomplete. It's an agent running a loop: **read context → act (edit files, run commands) → check the result → repeat** until it believes the task is done. It can read your whole repo, run your tests, call `git` and `gh`, and fetch docs.

That changes your job. You stop typing most of the code and become the **tech lead**: you define the problem, set constraints, decide architecture, and review everything. The engineers who get the most from these tools are the ones who are best at specifying and verifying, not the fastest typists.

### 1.2 The two constraints everything else follows from

**Constraint 1: the context window.** Everything in a session (your messages, every file Claude reads, every command's output) sits in one context window. It fills fast, and quality drops as it fills: Claude starts forgetting earlier instructions and making more mistakes. *Context is the scarcest resource you manage.* Almost every best practice below exists to protect it.

**Constraint 2: verification.** Claude stops when work *looks* done. If it has nothing to run that says pass or fail, "looks done" is the only signal, and you become the test suite. Give it a check (tests, a type check, a script, a screenshot to compare) and it fixes its own mistakes before you ever see them.

### 1.3 Who does what

| You decide and own | Claude does, under your direction |
| --- | --- |
| Architecture and the contracts between parts | Boilerplate, scaffolding, wiring |
| Acceptance criteria for every task | Implementation against an approved plan |
| What to cut when time runs short | Tests for the cases *you* name |
| Security calls (what may run, what may leave the laptop) | Refactors with tests green before and after |
| Reading every diff before it's committed | Debugging from logs and failing tests |
| Final judgement on whether it's good | First drafts of docs, README, CI files |

If you can't explain a piece of code Halo depends on, you don't own it yet. Each day ends with an understanding checklist for exactly that reason. Interviewers will ask.

### 1.4 The six rules for this project

1. **Contracts first.** Define the shared interfaces (the `HaloEvent` schema, Pydantic models, the skill interface) before building the parts that use them, then freeze them. Parallel work and Claude's accuracy both depend on this.
2. **Every task has a check Claude can run.** No check, no task. Write the check into the prompt.
3. **Plan before multi-file changes.** Use plan mode when you're unsure of the approach or more than ~3 files change. If you can describe the diff in one sentence, skip the plan.
4. **One task per session.** `/clear` between unrelated tasks. If you've corrected Claude twice on the same thing, `/clear` and restart with a better prompt.
5. **Commit after every green step.** Git is your real undo button. Claude's checkpoints are a convenience on top, not a replacement.
6. **Read every diff.** You're accountable for what ships. Skimming a 400-line diff you don't understand is how bugs and security holes get in.

---
## Part 2 — Set up Claude Code properly (Day 1 morning, about 2.5 hours)

Setup feels like overhead. It's the highest-leverage time you'll spend: every hour here saves several later, and the files you create become your reusable kit (Part 10).

### 2.1 Install the toolchain (Windows)

Run Claude Code **natively on Windows, not in WSL**. Halo is a desktop app with a native window, a global hotkey and a microphone, and all of those need real Windows. Claude Code must run where it can launch and test them.

1. **Git for Windows** (git-scm.com). Besides git, it installs Git Bash, which Claude Code uses for its Bash tool on Windows. Without it Claude Code falls back to PowerShell, and most examples you'll find assume Bash.
2. **Claude Code**, from PowerShell: `irm https://claude.ai/install.ps1 | iex`. Open a new terminal and run `claude --version`.
3. **Health check:** `claude doctor` prints install and settings diagnostics without starting a session.
4. **Log in:** run `claude` in any folder and follow the browser prompt.
5. **The rest of the stack:** `uv` (Python), Node 22 LTS, `gh` (GitHub CLI, then `gh auth login`), VS Code, Obsidian.
6. **Optional:** the Claude Code VS Code extension, which shows Claude's diffs inside your editor. You'll still run sessions in the terminal.

If Claude Code can't find Git Bash, set `CLAUDE_CODE_GIT_BASH_PATH` (for example `C:\Program Files\Git\bin\bash.exe`) under `"env"` in `~/.claude/settings.json`.

### 2.2 Model and effort strategy

`/model` switches the model and saves it as your default; inside the picker, the left and right arrows adjust *effort* (how hard the model thinks) on models that support it.

- **Planning, architecture, tricky debugging, security review:** the strongest model (Opus) at high effort. A wrong plan costs hours; a good plan is cheap.
- **Routine implementation against an approved plan:** a faster model (Sonnet) is usually enough and stretches your plan limits further.
- **Check spend daily** with `/usage` (alias `/cost`). If you hit plan limits mid-week, Part 9 says what to cut.

### 2.3 Create the repo

```bash
mkdir halo && cd halo
uv init --package --name halo
git init && git branch -M main
# Apache-2.0 license text from https://www.apache.org/licenses/LICENSE-2.0.txt saved as LICENSE
gh repo create halo --public --source . --push
```

Add these to `.gitignore` straight away, *before* you create any of the files:

```gitignore
.env
.env.*
!.env.example
CLAUDE.local.md
.claude/settings.local.json
.claude/worktrees/
__pycache__/
.venv/
node_modules/
dist/
build/
*.spec.bak
```

Then start Claude in the folder (`claude`) and run `/init`. It reads the project and drafts a `CLAUDE.md`. You'll replace most of it with the version in Appendix A, but `/init` is the right reflex for every new or inherited repo.

### 2.4 The "spec stack": documents that steer Claude

Claude starts every session knowing nothing except `CLAUDE.md` and what it reads. A small set of documents gives it the same picture of the project you have. Create the folder now; you'll fill these on Day 1.

| File | What it holds | Who writes it | When it changes |
| --- | --- | --- | --- |
| `docs/SPEC.md` | What Halo does, for whom, the features, what's out of scope | Claude, from an interview with you (Day 1) | Rarely |
| `docs/ARCHITECTURE.md` | Components, data flow, Nemotron model roles, folder layout | You + Claude in plan mode | When architecture changes |
| `docs/CONTRACTS.md` | The frozen interfaces: `HaloEvent`, `Intent`, `Plan`, `TaskBrief`, `MemoryItem`, the skill interface | You + Claude, then frozen | Only through the `/add-event` skill |
| `docs/PLAN.md` | The 8 days with "Done when" per day (paste from the Halo plan doc) | You | Daily ticks |
| `docs/DECISIONS.md` | One line per decision: date, decision, why, rejected alternative | Claude at handoff, you review | Every day |
| `PROGRESS.md` (repo root) | The handoff file: done, in progress, next, known issues, how to run | Claude via `/handoff` | End of every session |

`PROGRESS.md` is the single most useful habit in this playbook. It lets you `/clear` without fear: a fresh session reads it and knows exactly where things stand.

### 2.5 CLAUDE.md: the project brief Claude reads every session

`CLAUDE.md` loads at the start of every session, so every line costs context, every time. The test for each line: *would removing it make Claude make a mistake?* If not, cut it. Aim for under 100 lines; the docs warn that long files get partly ignored.

**Put in:** commands Claude can't guess, style rules that differ from defaults, test instructions, architecture decisions that aren't visible in code, Windows quirks, repo etiquette.
**Leave out:** anything Claude can learn by reading the code, standard conventions, long explanations, file-by-file descriptions, things that change weekly (those go in `PROGRESS.md`).

Two related files:

- **`CLAUDE.local.md`** (gitignored): your personal notes for this project, such as your test vault path and your shell.
- **`.claude/rules/*.md`**: rules that load *only* when Claude touches matching files, using a `paths:` frontmatter field. Python rules load only for `.py` files, UI rules only for `.tsx`. This is how you keep `CLAUDE.md` short.

One trap: `@path/to/file` imports inside `CLAUDE.md` are loaded at launch too, so they don't save context. To make a document available *on demand*, mention its path in plain text ("read `docs/CONTRACTS.md` before changing any event") and let Claude read it when needed.

The full `CLAUDE.md`, `CLAUDE.local.md` and four rule files are in Appendix A.

### 2.6 settings.json: permissions and hooks

`.claude/settings.json` is committed and shared; `.claude/settings.local.json` is personal and gitignored. Two sections matter most.

**Permissions** decide what runs without asking. Rules are checked in the order deny → ask → allow, and the first match wins.

- **allow** the safe, frequent commands: running tests, lint, type checks, `git status/diff/log/add/commit`.
- **ask** for anything that leaves your machine or is hard to undo: `git push`, dependency removal.
- **deny** what must never happen: reading `.env`, force-pushing, `rm -rf`.

Recent Claude Code versions start interactive sessions in **auto mode**, where a classifier reviews actions and blocks risky ones. Keep your allow and deny rules anyway: they're explicit, reviewable, and travel with the repo. `Shift+Tab` cycles permission modes, including plan mode.

**Hooks** are scripts Claude Code runs automatically at fixed points, such as after every file edit. The difference from `CLAUDE.md` matters:

- `CLAUDE.md` is *advice*. Claude usually follows it.
- A hook is *enforcement*. It always runs.

Anything that must happen every time with zero exceptions becomes a hook. Halo uses two:

1. **`format.py` (PostToolUse on Edit/Write):** formats and lints the file Claude just edited (`ruff` for Python, Prettier for TypeScript). Lint errors that can't be auto-fixed go to stderr with exit code 2, which the docs specify as the way to show a PostToolUse warning to Claude, so it fixes them in the same turn.
2. **`protect.py` (PreToolUse on Edit/Write):** blocks edits to `.env*`, `LICENSE` and lockfiles. It also blocks the frozen contracts unless the session was started with `HALO_CONTRACT_EDIT=1`, and blocks `tests/` when started with `HALO_LOCK_TESTS=1` (useful when you want Claude to make *existing* tests pass without touching them). Exit code 2 blocks the edit and tells Claude why.

Hooks are written in **Python** rather than Bash so they behave the same on Windows and Mac and don't depend on `jq`. Each hook reads a JSON object from stdin describing the tool call. Full `settings.json` and both scripts are in Appendix A. Run `/hooks` to see what's active.

### 2.7 Subagents: specialists with their own context

A **subagent** is a separate Claude instance with its own system prompt, tool list, model and, critically, **its own context window**. It does its job and returns only a summary. That gives you two benefits:

- **Context protection:** research that reads 40 files happens in the subagent's window, not yours.
- **Independent judgement:** a reviewer that didn't write the code isn't biased toward it.

You define them as Markdown files in `.claude/agents/` with frontmatter: `name`, `description` (tells Claude when to use it), `tools`, `model`. You can also add `isolation: worktree` to give one its own git checkout.

Halo uses five (full files in Appendix A):

| Subagent | Job | Tools | Model |
| --- | --- | --- | --- |
| `researcher` | Look up current library APIs (LangGraph, pywebview, sherpa-onnx, claude-agent-sdk) and report usage with sources | Read, Grep, Glob, WebFetch, WebSearch, Context7 | sonnet |
| `test-writer` | Write failing tests from a list of cases before implementation | Read, Grep, Glob, Edit, Write, Bash | sonnet |
| `reviewer` | Check a diff against the plan and spec; report only correctness and requirement gaps | Read, Grep, Glob, Bash | opus |
| `security-reviewer` | Trace untrusted input to tools, find secret leaks, check the policy engine | Read, Grep, Glob, Bash | opus |
| `ui-critic` | Screenshot the HUD in a browser and compare it to the design notes | Read, Playwright MCP | sonnet |

Invoke them by name ("use the reviewer subagent to…") or by typing `@` and picking one, which guarantees it runs.

### 2.8 Skills: your reusable workflows as slash commands

A **skill** is a folder in `.claude/skills/<name>/` containing a `SKILL.md` with instructions. Claude can load it automatically when relevant, or you run it as `/name`. Text after the command is passed in as `$ARGUMENTS`. Add `disable-model-invocation: true` for workflows you only want to trigger yourself.

Skills are how you stop retyping the same long prompts. Halo uses six (full files in Appendix A):

| Skill | What it does |
| --- | --- |
| `/kickoff` | Reads `PROGRESS.md` and today's section of `docs/PLAN.md`, then proposes today's task list and session plan |
| `/handoff` | Updates `PROGRESS.md` and `docs/DECISIONS.md`, runs the checks, commits |
| `/new-halo-skill <name>` | Scaffolds a Halo skill (`SKILL.md`, `skill.py`, tests, registry entry) |
| `/add-event <name>` | Adds a new event type everywhere it must exist: Pydantic model, JSON Schema export, TypeScript types, reducer case, tests |
| `/spike <question>` | Runs a time-boxed experiment in `spikes/` and records the answer in `spikes/RESULTS.md` |
| `/eval` | Runs the eval suite and summarises changes against the last report |

### 2.9 MCP servers for building

**MCP** (Model Context Protocol) servers give Claude extra tools. Every server's tools take context, so add only two:

```bash
# Real browser control: Claude can open the HUD dev page, click, and take screenshots
claude mcp add --scope project playwright -- npx @playwright/mcp@latest

# Current library documentation, so Claude doesn't rely on stale training data
claude mcp add --scope project --transport http context7 https://mcp.context7.com/mcp
```

`--scope project` writes them to `.mcp.json`, which you commit. Check they're connected with `/mcp`. For GitHub, use the `gh` CLI rather than a GitHub MCP server; CLI tools are the most context-efficient way to reach external services.

### 2.10 Status line

Run `/statusline show model, context used as a percentage, session cost and git branch`. Watching the context percentage is the easiest way to build the habit of clearing and compacting at the right time. Clear or hand off around 60–70%.

### 2.11 Setup checklist

- [ ] `claude doctor` is clean; Git Bash detected
- [ ] Repo on GitHub, Apache-2.0 `LICENSE`, `.gitignore` committed *before* `.env` exists
- [ ] `CLAUDE.md`, `CLAUDE.local.md`, `.claude/rules/*` in place
- [ ] `.claude/settings.json` with permissions and both hooks; `/hooks` lists them
- [ ] Edit a Python file through Claude and watch `ruff` run; try editing `.env` and watch it get blocked
- [ ] Five subagents in `.claude/agents/`, six skills in `.claude/skills/`
- [ ] `/mcp` shows playwright and context7 connected
- [ ] Status line shows context percentage
- [ ] `docs/` folder with empty SPEC, ARCHITECTURE, CONTRACTS, PLAN, DECISIONS; `PROGRESS.md` at the root

---
## Part 3 — The daily operating loop

### 3.1 The shape of a day

```
09:00  Kickoff session      /kickoff → today's task list, in plan mode → you approve
09:30  Task sessions        one fresh session per task (often 2 in parallel worktrees)
         each: explore → plan → test first → implement → check → review → commit
18:00  Review session       fresh session: reviewer subagent over the day's diff vs PLAN + SPEC
19:30  Dogfood              use Halo for real; write down what broke as tasks for tomorrow
21:30  Handoff              /handoff → PROGRESS.md, DECISIONS.md, commit, push, tag day-N
```

### 3.2 The task loop, step by step

Every task follows the same six steps. The keystrokes are what makes it fast.

**1. Start clean.** A fresh session (`claude`, or `/clear` in an open one). Name it: `/rename memory-index`. Named sessions can be resumed later with `claude --resume`, and `claude --continue` reopens the most recent one.

**2. Explore (plan mode).** Press `Shift+Tab` until the status bar shows plan mode, or type `/plan <task>`. In plan mode Claude reads and answers but can't edit. Point it at the specific files and docs. For anything that needs reading many files or looking up a library, say *"use subagents to investigate…"* so the reading happens outside your context.

**3. Plan.** Ask for a plan with: the files that will change, the steps in order, the tests that prove it works, and the risks. Press **`Ctrl+G`** to open the plan in your editor and fix it directly; that's faster than arguing in chat. Approve it to leave plan mode.

**4. Test first, then implement.** Have Claude write the tests for the cases you named, run them, and show them failing. Then implement until they pass. Showing the failure first proves the tests actually test something.

**5. Check and verify.** Claude runs the checks: tests, `ruff`, `pyright`, and for UI a screenshot. Ask for **evidence**, meaning the command output, not "all tests pass". For larger changes, run the `reviewer` subagent or the bundled `/code-review` skill on the diff. A fresh context finds what the author missed.

**6. Commit.** "Commit with a conventional commit message." Then `/clear` before the next task.

**Course correction (use it early):**

| Key or command | What it does | When |
| --- | --- | --- |
| `Esc` | Stops Claude mid-action; context is kept | The moment you see it heading the wrong way |
| `Esc Esc` or `/rewind` | Opens the rewind menu: restore code, conversation or both to an earlier prompt, or summarise from a point | A risky experiment failed; undo it cleanly |
| `/clear` | Empty context, new conversation | Between tasks; after two failed corrections |
| `/compact <focus>` | Summarises the conversation to free space, keeping what you name | Long task, context above ~60% |
| `/context` | Shows what's using the context window | When quality drops and you don't know why |
| `/btw <question>` | Side question whose answer never enters the conversation | "What was that flag again?" |

Checkpoints only track edits made through Claude's file tools, not changes made by shell commands. That's another reason to commit often.

### 3.3 Parallel sessions with worktrees

A **git worktree** is a second working folder for the same repo, on its own branch. Two Claude sessions in two worktrees can't overwrite each other's files.

```bash
claude --worktree hud        # session 1: UI work, in .claude/worktrees/hud on branch worktree-hud
claude --worktree mood       # session 2, in another terminal: backend mood engine
```

Add a `.worktreeinclude` file (gitignore syntax) listing `.env`, so your keys are copied into each new worktree automatically. When you exit, Claude offers to keep or remove the worktree; merge the branch through a PR or `git merge`.

**Rules for parallel work, solo:**

- Run parallel sessions only on **independent areas that touch different files** (backend vs UI), and only **after the contract between them exists**.
- **Two sessions at most.** Your review time is the bottleneck, not Claude's typing speed. A third session produces diffs you won't read properly.
- While one session is working, read the other's diff. Don't use the waiting time to start a third.

### 3.4 Context hygiene rules

- Keep `CLAUDE.md` short; move file-type rules into `.claude/rules/`.
- Point to files with `@path` in your prompt instead of pasting their contents.
- For a long log, save it to a file and point to the file.
- Research and broad exploration go to subagents.
- One task per session. The "kitchen sink" session (a task, an unrelated question, back to the task) is the most common way quality degrades.
- If a correction keeps getting lost, it's a rule (add it to the right rules file) or a check (make it a hook or a test).

### 3.5 Review discipline

- Read every diff before committing: `git diff`, or the VS Code diff view.
- Ask for evidence: test output, the command that ran and what it returned, a screenshot.
- For anything over ~150 lines, run the `reviewer` subagent with the plan as the reference. Tell it to report only correctness and requirement gaps; reviewers asked to "find issues" always find some, and chasing style nits leads to over-engineering.
- Use `/simplify` occasionally for a cleanup pass. It looks for reuse, simplification and efficiency, not bugs, so pair it with `/code-review` for bugs.
- Run `/security-review` on Day 6 and Day 8. It reviews your branch's diff against `origin` for injection, auth and data-exposure risks.

### 3.6 Commit and branch discipline

- **Conventional Commits:** `feat(memory): add hybrid retrieval with RRF`, `fix(hud): hold mood for 700 ms`, `test(policy): cover tainted args`. Claude writes good ones if CLAUDE.md asks.
- **One logical change per commit.** A commit should be revertable on its own.
- **Feature branches + PRs, even solo.** One PR per day or per feature, created with `gh pr create`. CI runs on every PR, and the history reads like a professional repo, which hiring managers do look at.
- **Tag each finished day:** `git tag day-3 && git push --tags`.

---

## Part 4 — The prompt playbook

### 4.1 Anatomy of a good prompt

Every implementation prompt has six parts. Leave one out and you'll pay for it in corrections.

1. **Goal:** one sentence on what should exist afterwards.
2. **Context:** the files (`@halo/memory/retrieve.py`), docs (`docs/CONTRACTS.md`) and patterns to follow ("follow the structure of `skills/app_open/`").
3. **Constraints:** libraries allowed, performance limits, Windows compatibility, "don't change the event schema".
4. **Acceptance criteria:** the concrete cases that must work.
5. **Verification:** the exact commands Claude must run and show output from.
6. **Out of scope:** what *not* to touch. This prevents half of all scope creep.

**Weak:** *"add memory search"*

**Strong:**

```text
Implement hybrid retrieval in @halo/memory/retrieve.py.

Context: items live in the SQLite index built by @halo/memory/index.py
(FTS5 table `items_fts`, sqlite-vec table `items_vec`). MemoryItem is defined
in docs/CONTRACTS.md.

Requirements:
- search(query, k=8) runs FTS5 and vector search (top 20 each) and merges them
  with reciprocal rank fusion, score = sum(1 / (60 + rank)).
- Drop expired items; multiply score by 1.2 for trust == "high".
- assemble_context(query, budget_tokens=1500) fills the budget best-first and
  never includes items from notes with privacy: local.

Tests first, in tests/memory/test_retrieve.py:
- an exact-name query ranks the keyword hit first
- a paraphrase query finds the semantic match
- an expired item never appears
- a privacy: local item never appears in assemble_context output
- RRF result is identical when the two input lists are swapped

Run `uv run pytest tests/memory -q` and show the output, red then green.
Out of scope: index.py, the extraction pipeline, any UI.
```

### 4.2 Templates

Copy these, fill the brackets, and keep refining them. The best ones become skills.

**P1 · Interview me, then write a spec** (fresh session, big features only)

```text
I want to build [feature]. Read docs/SPEC.md and docs/ARCHITECTURE.md first.
Interview me in detail using the AskUserQuestion tool about implementation,
UX, edge cases, failure modes and trade-offs. Skip obvious questions; dig into
the hard parts I haven't considered. When we've covered everything, write the
spec to docs/specs/[feature].md: files and interfaces involved, out of scope,
and an end-to-end verification step.
```

Then start a *new* session to implement it. The new session gets clean context and a written spec.

**P2 · Explore** (plan mode)

```text
Use subagents to investigate [question]: how [library/part] works, which
existing code I should reuse, and what could conflict. Report file paths and a
short summary. Don't change anything.
```

**P3 · Plan** (plan mode)

```text
Plan [task] per docs/specs/[feature].md. Give me: files to create or change,
steps in order, the tests that prove each step, risks and how you'll detect
them, and anything in the spec you think is wrong. Keep to the interfaces in
docs/CONTRACTS.md.
```

**P4 · Tests first**

```text
Use the test-writer subagent to write failing tests in [path] for these cases:
[list]. No mocks of the unit under test; use fixtures in tests/fixtures/.
Run them and show they fail for the right reason.
```

**P5 · Implement the approved plan**

```text
Implement step [n] of the plan. Make the failing tests in [path] pass without
modifying them. Run `uv run pytest [path] -q`, `uv run ruff check .` and
`uv run pyright` and show the output. Stop after this step.
```

**P6 · Fix a bug**

```text
Symptom: [what happens, exact error or log in @logs/x.txt].
Expected: [what should happen]. Likely area: [files].
First write a failing test that reproduces it. Then fix the root cause, not the
symptom; don't suppress errors or loosen types. Show the test going red → green.
```

**P7 · Visual UI iteration** (with Playwright MCP)

```text
Run `npm run dev` in ui/ and open http://localhost:5173/moods with the
Playwright tools. Screenshot each mood. Compare against the mood table in
docs/ARCHITECTURE.md (face, ring colour, accessory). List every difference,
fix them, and screenshot again. Repeat until they match, max 3 rounds.
```

**P8 · Safe refactor**

```text
Refactor [module] to [goal]. Behaviour must not change. Run the full test
suite before and after and show both results. If a test needs to change, stop
and explain why instead of changing it.
```

**P9 · Adversarial review** (end of a feature)

```text
Use the reviewer subagent to review the diff on this branch against
docs/specs/[feature].md and the plan. Check every requirement is implemented,
listed edge cases have tests, and nothing outside scope changed. Report only
gaps that affect correctness or the stated requirements.
```

**P10 · Learn it** (for your understanding checklist)

```text
Explain how [file/flow] works as if I'm going to be interviewed on it: the
data flow, why each design choice was made, what would break if [X] changed.
Then ask me 5 questions and correct my answers.
```

When you're learning a new library, switch the output style with `/config` to **Explanatory** so Claude explains its choices as it works. Switch back to the default for speed.

### 4.3 Prompting habits that compound

- **Name files, not areas.** "In `halo/core/router.py`" beats "in the router".
- **Point to an existing pattern.** "Follow how `skills/app_open/` is structured" gets consistent code.
- **Paste images.** Screenshots of the HUD, error dialogs and design sketches go straight into the prompt.
- **Ask for evidence, not assurances.**
- **Stop early.** Press `Esc` the moment it goes wrong; a ten-second correction beats a ten-minute rewind.
- **When Claude does something great, notice what you did.** Turn it into a template or a skill.

---
## Part 5 — The 8-day build

Each day has the same layout:

- **Goal and Done when:** from the Halo plan doc, adjusted for the new dates.
- **Claude Code skills you'll practise:** the technique that day is built around.
- **Sessions:** the sessions in order, with mode and the prompt to start each one. "WT" means run it in its own worktree, in parallel with the previous session.
- **Gate:** what must be true before you hand off.
- **Understanding checklist:** questions about Halo *and* about Claude Code, answered without notes.

Prompts are starting points. Adapt them, and save the ones that work as skills.

---

### Day 1 — Sat Oct 10: foundations, spec, contracts, spikes

**Goal.** A configured repo, a written spec, frozen contracts, every unknown answered with a number, and CI running green. No product features yet, deliberately.

**Claude Code skills:** `/init` and CLAUDE.md · settings, permissions, hooks · interview → spec · plan mode · parallel worktrees · `/spike` and `/handoff` skills.

**S1 · Setup (2.5 h).** Work through Part 2 and its checklist. Save this playbook into the repo as `docs/PLAYBOOK.md`, ask Claude to create the config files from Appendix A, then review each one.

```text
Create the files listed in @docs/PLAYBOOK.md Appendix A: CLAUDE.md,
.claude/rules/*, .claude/settings.json, .claude/hooks/format.py and protect.py,
.claude/agents/*, .claude/skills/*, .worktreeinclude, PROGRESS.md and the docs/
skeleton. Use the contents exactly. Then show me `git status`.
```

Then test the hooks yourself: ask Claude to add a line to `.env` (it must be blocked) and to create a badly formatted Python file (it must be reformatted).

**S2 · Spec interview (45 min, fresh session, strongest model).** Paste the Halo plan doc into `docs/PLAN.md` and its architecture section into `docs/ARCHITECTURE.md` first.

```text
I'm building Halo: read docs/PLAN.md and docs/ARCHITECTURE.md. Interview me
using the AskUserQuestion tool about anything unclear or risky: which skills
are in v0.1, what "done" means for each, approval rules, what may leave the
laptop, failure behaviour, Windows specifics. Then write docs/SPEC.md:
goals, users, features with acceptance criteria, non-goals, constraints
(Nemotron on Nebius Token Factory only for LLM calls, Python 3.12, Windows
first), and an end-to-end demo script.
```

**S3 · Contracts (1.5 h, plan mode, strongest model).** This is the most important session of the week. Every other part depends on it.

```text
/plan Design the shared contracts in halo/core/contracts.py using Pydantic v2,
based on docs/SPEC.md and the event contract in docs/ARCHITECTURE.md:
HaloEvent (with the full type Literal), Intent, Step, Plan, TaskBrief, Review,
MemoryItem, MemoryCandidate, Expense, ApprovalRequest, ApprovalDecision,
SkillManifest, and a Skill Protocol with `async def run(ctx, args)`.
Also: a script `python -m halo.core.export_schemas` that writes JSON Schema for
each model to schemas/, and a test that fails if schemas/ is out of date.
Write docs/CONTRACTS.md explaining each type in 2-3 lines.
```

Review the plan line by line before approving; then implement, run tests, and commit. From now on `protect.py` blocks edits to the contracts unless you start Claude with `HALO_CONTRACT_EDIT=1`. The only sanctioned way to change them is `/add-event`, which updates every consumer together.

**S4 · Spikes, model side (WT `spikes-models`).**

```text
/spike Token Factory: for Nemotron 3 Nano, Super and Ultra, run 10 tool calls
and 10 JSON-schema calls each with the contracts' Intent model. Record valid
output rate, median latency and cost per call. Also list available models and
whether an embedding model exists. Load the key with python-dotenv inside the
script; never print it.
```

Claude can't read `.env` (your deny rule), but scripts it writes can load it at runtime. The key never enters the conversation. That's the pattern for every secret this week.

**S5 · Spikes, local side (WT `spikes-local`, in parallel).**

```text
/spike Local runtime: (1) sherpa-onnx with the Nemotron ASR or Parakeet ONNX
model: a script that records 5 s from the mic, or reads a .wav with --wav, and
prints the transcript and latency after speech ends. (2) pywebview: a
frameless, always-on-top 260x44 window at top centre that a JS call resizes to
420x600. (3) Create tests/fixtures/demo_repo: a tiny FastAPI app with one
passing test, its own git repo. Then run claude-agent-sdk against it, print
every message type, and confirm can_use_tool fires.
```

Claude writes the scripts; *you* run the microphone and window ones, because they need your hardware and screen. Paste the output back.

**S6 · CI skeleton (30 min).**

```text
Write .github/workflows/ci.yml: on push and pull_request, set up uv and
Python 3.12, run `uv run ruff check .`, `uv run ruff format --check .`,
`uv run pyright`, `uv run pytest -m "not live" -q`, and a gitleaks secret scan.
Push to a branch, open a PR with gh, and watch the run with `gh run watch`.
Fix until green.
```

CI from day one is the industry norm: every later PR is checked automatically, so Claude's mistakes surface in minutes, not on Day 8.

**S7 · Handoff.** `/handoff`, merge the PR, `git tag day-1`.

**Gate.** `spikes/RESULTS.md` has a number for every spike and a written decision for each; contracts committed and protected; `docs/SPEC.md` exists; CI green on `main`.

**Understanding checklist**

- [ ] Why freeze contracts before any parallel work?
- [ ] What's the difference between a line in CLAUDE.md, a rule in `.claude/rules/`, and a hook? When would you use each?
- [ ] How does a script use your API key without Claude ever seeing it?
- [ ] Why did the spikes run in worktrees, and what did `.worktreeinclude` do?

---

### Day 2 — Sun Oct 11: the core brain

**Goal.** Request → router → planner → executor, with every step emitted as a `HaloEvent`, streamed over WebSocket, saved to JSONL, and printed by the CLI. Done when `uv run halo "open VS Code"` opens VS Code with the full event stream visible, and the router scores at least 18/20.

**Claude Code skills:** researching current library APIs with a subagent and Context7 · test-driven development · plan mode for multi-file work · recorded model responses for deterministic tests · a parallel worktree for an independent component.

**S1 · Research before code (plan mode).** LangGraph changes quickly, and stale API knowledge is the commonest way AI-written code goes wrong with fast-moving libraries.

```text
Use the researcher subagent with Context7 to find the CURRENT LangGraph APIs
for: StateGraph with typed state, conditional edges, the SQLite checkpointer,
interrupts with Command(resume=...), and emitting custom stream events from
inside a node. Write docs/notes/langgraph.md: one short code example per topic
with the source URL. No implementation yet.
```

**S2 · Model client and cascade (TDD).**

```text
Implement halo/models/client.py and cascade.py per docs/SPEC.md and the
Nemotron roles in docs/ARCHITECTURE.md. Tests first in tests/models/:
- call() returns a parsed Pydantic object and token usage
- a validation failure retries once with the error appended, then escalates
- confidence < 0.7 from Nano escalates to Super, and the escalation is logged
- cost.updated events carry ₹ per call from a price table in config.toml
Use pytest-recording (vcrpy) cassettes for the HTTP calls and filter the
Authorization header from cassettes. Show red, then green.
```

**Recorded responses ("cassettes")** save a real HTTP response the first time a test runs, then replay it every time after. Tests become fast, free and deterministic. Re-record deliberately (`--record-mode=rewrite`) when prompts change. The header filter keeps your key out of the repo.

**S3 · Router and golden set.**

```text
Implement halo/core/router.py: Nano returns an Intent. Create
evals/router_golden.yaml with 20 utterances covering every skill, including
5 ambiguous ones. Add a pytest marked `live` that runs them and reports the
score. Run it once live and show the score.
```

**S4 · Graph, planner, skill registry.**

```text
/plan Build halo/core/graph.py (router → planner (conditional) → executor →
finalize, SQLite checkpointer, thread_id = run_id), planner.py (Super returns
Plan), and skills/registry.py loading skills/<name>/SKILL.md + skill.py.
Follow docs/notes/langgraph.md exactly. Then use /new-halo-skill app_open with
an allowlist from config.toml.
```

**S5 · Event bus, API, recorder, CLI (WT `api`, in parallel with S4).** This only depends on the contracts, so it can run alongside S4.

```text
Implement halo/api/events.py (asyncio pub/sub of HaloEvent), halo/api/server.py
(FastAPI: POST /run, POST /approve, WS /events), halo/telemetry/recorder.py
(append every event to ~/.halo/runs/YYYY-MM-DD.jsonl) and a `halo` CLI that
prints events live with rich. Tests: a WebSocket client receives events in
order; the recorder writes valid JSONL that parses back into HaloEvent.
```

**S6 · Merge, review, handoff.** Merge the `api` worktree branch, then run the reviewer:

```text
Use the reviewer subagent on today's diff against Day 2 "Done when" in
docs/PLAN.md and docs/SPEC.md. Report only gaps that affect correctness.
```

Fix what matters, `/handoff`, tag `day-2`.

**Understanding checklist**

- [ ] What does the checkpointer store, and how does that make approvals possible tomorrow?
- [ ] What's a cassette, and why must the Authorization header be filtered?
- [ ] Why research LangGraph's API before letting Claude write graph code?
- [ ] Which two pieces of today's work could safely run in parallel, and why?

---

### Day 3 — Mon Oct 12: the HUD and the character

**Goal.** Halo lives at the top of the screen, reacts to every event, expands on click, and pauses a run until you approve. Done when "open Spotify" (not allowlisted) makes Halo think, raise its hand, show the permission card, and open Spotify after you press Enter, then look delighted for 2 seconds.

**Claude Code skills:** backend and frontend in parallel worktrees · visual iteration with Playwright screenshots · designing for testability (a mock event stream) · rewind for risky animation experiments · giving Claude images as specs.

**Design decision first.** Claude can't see a native pywebview window, but it *can* screenshot a web page with Playwright. So build the UI as a normal web app that runs in the browser at `http://localhost:5173`, with a `?mock=` parameter that replays a recorded JSONL run from Day 2. pywebview simply hosts the same build. This one decision lets Claude check its own UI work all day.

**S1 · Mood engine (WT `mood`).**

```text
Implement halo/character/mood.py from the mood table in docs/ARCHITECTURE.md:
event → mood rules, the priority order, and a 700 ms minimum dwell. Inject the
clock so tests control time. Test every rule, every priority conflict and the
dwell. Then halo/character/lines.py: Nano status lines (max 7 words) with a
400 ms timeout and a template fallback, cached by (skill, event type, title).
```

**S2 · UI scaffold and reducer (WT `hud`, in parallel).**

```text
Scaffold ui/ with Vite, React, TypeScript, Tailwind, Framer Motion, Rough.js
and zustand. Generate TypeScript types from schemas/ with
json-schema-to-typescript (npm script `gen:types`) and add a test that fails
if they're stale. Implement useHaloEvents(): WebSocket or ?mock=<file> →
reducer → store (runs, timeline, agent tree, approvals, mood). Copy one
recorded run from ~/.halo/runs into ui/src/test/fixtures/ and write Vitest
tests for the reducer against it.
```

The generated types and their staleness test are your **contract parity check**: Python and TypeScript can't drift apart without a red test.

**S3 · The mascot (in the `hud` worktree).** Export the mood sheet and HUD sketches from the plan doc as images and paste them in.

```text
[paste mood sheet image] Build <HaloMascot mood agents /> in
ui/src/mascot/: SVG layers (body, eyes, mouth, halo ring, accessory slot,
orbiting mini-halos), drawn with Rough.js. Boiling outline (reseed ~8 fps)
only while busy. Blink every 3-6 s, breathing scale 1.00 to 1.03 over 3 s.
One Framer Motion variant per mood. Add a /moods page showing all 13.
Then use Playwright to screenshot /moods and compare with the image and the
mood table; fix differences; max 3 rounds.
```

When an animation experiment goes badly, `Esc Esc` → restore code to before it, rather than asking Claude to undo by hand. Then use the `ui-critic` subagent for a fresh-eyes pass.

**S4 · Bar, card, panel, and the native host.**

```text
[paste HUD sketch] Build the collapsed bar, permission card and expanded
panel exactly as sketched. Keyboard: Enter allow, Esc deny/collapse.
Then halo/app.py: start uvicorn in a thread and open pywebview frameless,
always on top, 260x44 at top centre, with js_api resize/move/open_path.
Wire approval.requested → card → POST /approve → Command(resume=...).
```

You test the native window yourself: run `uv run halo-app`, try the Spotify flow, and paste a screenshot if something's off.

**S5 · Merge, review, handoff.** Merge both worktrees, run the reviewer against Day 3 Done-when, `/handoff`, tag `day-3`.

**Understanding checklist**

- [ ] Why does the mood live in Python and not in React?
- [ ] How does the mock event stream let Claude verify UI work it can't otherwise see?
- [ ] What stops the Python and TypeScript event types from drifting apart?
- [ ] Trace an approval click from the button to the paused LangGraph node.

---

### Day 4 — Tue Oct 13: memory

**Goal.** Halo remembers across restarts, every memory records its source and trust, and deleting a line in Obsidian really forgets it. Done when a restart still answers "what did I pick for the HUD window?" with a link to the note, and deleting that line makes Halo say it doesn't know.

**Claude Code skills:** a short spec interview for a subtle subsystem · property-based testing · fixture data · `/compact` with focus during a long session · a frontend task in a second worktree.

**S1 · Memory spec (30 min).** Memory has subtle rules (contradictions, expiry, privacy), so spend a short interview here.

```text
Interview me with AskUserQuestion about Halo's memory semantics: what counts
as a memory, source and trust levels, expiry, contradictions, forgetting,
privacy: local, and what the user reviews. Then write docs/specs/memory.md
with acceptance criteria and examples.
```

**S2 · Vault parser and writer (TDD + Hypothesis).**

```text
Implement halo/memory/vault.py per docs/specs/memory.md: parse notes into
MemoryItems from frontmatter and bullets with inline fields
[src:: you] [trust:: high] [at:: 2026-10-10] ^m-4f2a, and write changes back.
Tests: fixture vault in tests/fixtures/vault/, plus Hypothesis property tests:
parse → write → parse is identical; Obsidian block IDs survive; unrelated
lines in a note are untouched byte-for-byte.
```

**Property-based tests** (the Hypothesis library) generate hundreds of random inputs and check that a rule always holds, such as "writing then re-reading changes nothing". They find edge cases neither you nor Claude would list.

**S3 · Index and file watching.**

```text
Implement halo/memory/index.py: SQLite with FTS5 and sqlite-vec, embeddings
from the source chosen in spikes/RESULTS.md, re-index on change with watchdog.
Windows emits several events per save: debounce 300 ms. Test: editing and
deleting a fixture note updates the index.
```

**S4 · Retrieval.** Use the full example prompt from Part 4.1. When context passes ~60%, run `/compact keep the list of changed files, test commands and open issues`.

**S5 · Extraction and the Memory tab (UI part in WT `memory-ui`).**

```text
Backend: halo/memory/extract.py: Nano extracts MemoryCandidates after each
run; skip near-duplicates (cosine >= 0.9); mark contradicted facts superseded;
emit memory.proposed. UI (other worktree): the Memory tab with Approve, Edit
and Reject that call a new POST /memory/decide endpoint.
```

Adding the endpoint may need a new event or model. Use `/add-event` so every consumer changes together.

**S6 · Skills and the restart test.**

```text
/new-halo-skill memory_remember, then memory_recall (answers with obsidian://
links) and memory_forget (approval, delete lines, memory.forgotten). Write an
end-to-end test: remember → restart the app object → recall → delete the
line on disk → recall says unknown.
```

Review, `/handoff`, tag `day-4`.

**Understanding checklist**

- [ ] Why does RRF work without normalising the two searches' scores?
- [ ] What did a Hypothesis property test catch that example tests wouldn't?
- [ ] Why must a fact learned from a web page never be able to trigger an action?
- [ ] When do you `/compact` versus `/clear`?

---

### Day 5 — Wed Oct 14: the coding work session

**Goal.** "Let's get to work" → Halo recalls where you stopped → a task brief → you approve → Claude Code edits in an isolated worktree with live events → Halo runs your tests itself → Nemotron Ultra reviews → merge. Done when this works on one of your real repos.

**Claude Code skills:** building on the Claude Agent SDK · exploring tool output with headless `claude -p` · replaying recorded transcripts as fixtures · the writer/reviewer two-session pattern · dogfooding.

Today you use Claude Code to build a tool that drives Claude Code. Understanding its event stream from the inside is the point.

**S1 · Study the stream first.**

```text
In tests/fixtures/demo_repo run:
claude -p "add a GET /health endpoint with a test" --output-format stream-json
--verbose --allowedTools "Read,Edit,Bash(uv run pytest *)"
Save the output to tests/fixtures/claude_stream/health.jsonl. Then summarise
every message type in it and which HaloEvent each should map to. Write the
mapping table into docs/notes/claude_stream.md.
```

The saved transcript becomes a test fixture: you can test the adapter by replaying it, with no live calls and no cost.

**S2 · Project registry and repo map (TDD).**

```text
Implement the Projects/<name>.md frontmatter schema (path, default_branch,
test_cmd, lint_cmd, stack, claude_session_id, last_stop) and
halo/tools/repo_map.py (git ls-files, key files, top-level symbols via ast for
Python and regex for TS, cached by HEAD hash). Test on tests/fixtures/demo_repo.
```

**S3 · Task brief and worktrees.**

```text
Implement skills/code_task with modes explain, plan, implement. Super writes a
TaskBrief from the repo map, project note and relevant memories; the approval
card shows it and allows editing. halo/tools/git_ops.py creates
../.halo-worktrees/<repo>/<slug> on branch halo/<slug> and removes it on discard.
```

**S4 · The worker adapter.**

```text
/plan halo/tools/claude_worker.py using claude-agent-sdk: cwd = worktree,
permission_mode acceptEdits, pre-approved Read/Edit/Glob/Grep and
Bash(<test_cmd> *), Bash(git diff *), Bash(git status *). Other tool requests
go through can_use_tool → an asyncio Future resolved by POST /approve. Map
messages to HaloEvents per docs/notes/claude_stream.md (sub-agents via
parent_tool_use_id). Enforce max_turns, a ₹ cap and a timeout that interrupts
cleanly. Tests replay tests/fixtures/claude_stream/*.jsonl through the mapper.
Also define a CodingWorker Protocol so another worker can replace it.
```

**S5 · Verify, review, finish.**

```text
After the worker finishes: Halo runs test_cmd itself in the worktree with a
timeout, collects the diff, and Ultra returns a Review against the brief's
acceptance criteria. Result card: Open in VS Code (`code <worktree>`), Merge
(local, after approval, never pushes), Iterate (resume the saved session with
feedback), Discard. Append a session log to the project note and set last_stop.
Then the work.start skill for "let's get to work".
```

**S6 · Writer/reviewer.** Open a *second* terminal with a fresh session:

```text
Review the code_task skill and claude_worker on this branch as a skeptical
senior engineer: what happens on timeout, on a denied permission, on a dirty
worktree, on a test command that hangs, on a repo with no tests? List
concrete failure cases with file:line.
```

Paste the findings into the first session to fix. A separate session reviews without the author's bias.

**From tonight, dogfood:** at least one task a day goes through Halo itself. It's the fastest way to find real bugs, and it's an honest line for your video.

**Understanding checklist**

- [ ] Why record a real `stream-json` run before writing the adapter?
- [ ] Why does Halo run the tests itself instead of trusting the worker's report?
- [ ] How does a permission request inside Claude Code reach your HUD and come back?
- [ ] Why do writer and reviewer sit in separate sessions?

---

### Day 6 — Thu Oct 15: security and voice

**Goal.** Nothing Halo reads can make it act; you can see every byte that left the laptop; and you can drive it by voice. Done when the hidden-instruction page is blocked with the shield and banner, the Ledger shows salary never left, and "let's get to work" starts within 1.5 s of you finishing speaking.

**Claude Code skills:** threat modelling in plan mode · attack tests written *before* the defences · `HALO_LOCK_TESTS` so Claude can't weaken them · the `security-reviewer` subagent and `/security-review` · building code Claude can't run itself (hardware), using fakes and your logs.

**S1 · Threat model (plan mode, strongest model).**

```text
/plan Build docs/THREAT_MODEL.md for Halo: list every untrusted input (web
pages, fetched READMEs, PDFs, memory from web sources, Claude Code output),
every sink (shell, file writes, email/messages, git merge, cloud prompts),
and each path from input to sink, with the control that should stop it
(Reader, Tainted[T], policy table, approvals, privacy filter). Include the
attacks from the Halo plan Day 5 section.
```

**S2 · Attacks first.**

```text
Create evals/injection_suite/: 15 attack fixtures (pages, READMEs, emails,
a poisoned memory) with the attacker's goal for each, and
tests/security/test_injection.py asserting each attack fails: no blocked tool
runs, a policy.blocked event is emitted, the user task still completes where
possible. Run them: they should FAIL now. Commit.
```

**S3 · Defences, with the tests locked.** Start this session with the tests locked, so Claude has to make the attack tests pass rather than edit them. In Git Bash: `HALO_LOCK_TESTS=1 claude`. In PowerShell: `$env:HALO_LOCK_TESTS=1; claude`.

```text
Implement halo/security/taint.py (Tainted[T], contains_taint), reader.py (Nano,
no tools, strict output schema), and policy.py (risk × taint × trust → allow,
ask or deny; high risk never "always"). Make tests/security pass without
editing tests. Then the web.read skill through the Reader.
```

**S4 · Egress ledger and caps.**

```text
Model client: record memory item IDs and byte counts per call, emit
egress.sent, and raise if text from a privacy: local note appears in any
prompt (test it). Per-run and per-day ₹ caps from config.toml. Ledger tab in
the HUD.
```

**S5 · Independent security review.**

```text
Use the security-reviewer subagent on halo/security, halo/models and
halo/tools against docs/THREAT_MODEL.md. Report exploitable paths only, with
file:line and a concrete attack.
```

Then run `/security-review` for a second opinion on the branch diff. Fix, and add a test for every confirmed finding.

**S6 · Voice.** Claude can't hear your microphone, so design for it:

```text
Implement halo/voice/hotkey.py (pynput, hold Ctrl+Space) and asr.py
(sherpa-onnx streaming + Silero VAD) per spikes/RESULTS.md. Add a --wav
input path and a FakeMic for tests; unit-test end-of-speech detection with
fixture wavs in tests/fixtures/audio/. Log timings at each stage.
```

You run it with your real microphone and paste the timing log back; Claude tunes from the log.

`/handoff`, tag `day-6`.

**Understanding checklist**

- [ ] Why write the attack tests before the defences?
- [ ] What does `HALO_LOCK_TESTS` protect against, and how does the hook enforce it?
- [ ] Walk through what happens when a tainted value reaches a high-risk tool.
- [ ] How do you get Claude to work on code that needs hardware it can't use?

---

### Day 7 — Fri Oct 16: life skills and golden tasks

**Goal.** Trip research with parallel helpers, expenses calculated in code, the app launcher, and the morning brief, plus golden tasks written from real use. Done when the Goa trip request sends five helpers out and writes a sourced note, expenses log and query correctly, and the brief works when triggered by hand.

**Claude Code skills:** speed through reuse (`/new-halo-skill`) · two parallel worktrees on independent skills · turning your flight-recorder logs into eval data · `/goal` for a multi-step finish line.

**S1 · Trip research (WT `trip`).**

```text
/new-halo-skill trip_plan. Super plans five sub-agents (stay, transport,
places, season, budget) started with LangGraph Send; each searches with Tavily,
reads pages via web.read (Reader), returns Tainted findings with URLs, max 6
tool calls. The budget helper only calls finance.monthly_surplus() locally.
Ultra writes Trips/<slug>.md with only cited facts. Calendar hold via a Google
Calendar MCP server behind a medium-risk approval; fall back to an .ics file.
Tests with recorded responses.
```

**S2 · Expenses (WT `expenses`, in parallel).**

```text
/new-halo-skill expense_log and expense_query. Nano parses text into Expense;
SQLModel table; mirror to Finance/YYYY-MM.md (privacy: local). Queries: Nano
returns an ExpenseQuery (category, date range, aggregation) and SQL computes
the answer. The model never adds numbers. Category budgets from the Finance
note's frontmatter. Tests: 10 parse cases, 8 query cases with exact totals.
```

**S3 · Launcher and morning brief.** App aliases from `Profile.md`, APScheduler brief at 09:00 and end-of-day check at 19:00, both triggerable from the CLI.

**S4 · Golden tasks from real use.**

```text
Read my flight-recorder logs in ~/.halo/runs/ from the last 4 days. Draft 25
golden tasks in evals/golden_tasks/*.yaml (5 each: coding, memory, research,
expenses, launcher/misc): input, fixtures, deterministic checks, and a rubric
where judgement is needed. Mark expected values TODO where you're unsure;
I'll fill them in.
```

You fill in and correct the expected outcomes. Golden tasks are *your* definition of correct; Claude only drafts them.

`/handoff`, tag `day-7`.

**Understanding checklist**

- [ ] Why does the budget helper run locally while the other helpers use the cloud?
- [ ] Why must SQL, not the model, add up expenses?
- [ ] Why build golden tasks from your own usage logs instead of inventing them?

---

### Day 8 — Sat Oct 17: evals, release and docs

**Goal.** Real numbers in the README, a tagged release with Windows and Mac builds, onboarding that works on a clean machine, and a final security pass. Done when download → onboarding → first successful command takes under 5 minutes on a fresh Windows user account.

**Claude Code skills:** `/goal` · a release CI matrix · `gh run watch` · writing docs from code and real outputs · final review passes (`/simplify`, `/code-review`, `/security-review`).

**S1 · Evals with a goal.**

```text
/goal evals/report.md exists with golden-task success, judge agreement with
my labels in evals/labels.yaml, injection attack success with defences off vs
on plus utility under attack, and the Nano/Super/cascade table, all produced
by `uv run python evals/run_evals.py` from real runs, not estimates.
```

Before the goal can complete, Claude runs the judge once and writes `evals/labels.yaml` with the judge's verdicts and an empty column for yours. You fill in your own verdicts for the 25 tasks, and the agreement rate is computed from that.

`/goal` keeps Claude working across turns until a separate evaluator confirms the condition holds. It's the right tool for a finish line with several parts. Check the numbers yourself afterwards; never put a number in the README you haven't seen produced.

**S2 · Release pipeline.**

```text
Write .github/workflows/release.yml: on tags v*, a matrix of windows-latest
and macos-latest; build ui/, then PyInstaller onedir from halo.spec (include
ui/dist, exclude the speech model, which downloads on first run); zip and
attach to a GitHub Release. Push tag v0.1.0-rc1 and watch with gh run watch.
Fix until both builds succeed, then download the Windows zip and list its
contents.
```

**S3 · Onboarding, demo vault, demo key.** First-run onboarding in the HUD, the demo vault and persona, and the Cloudflare Worker that holds the demo key. Claude writes the Worker; **you** run `npx wrangler secret put TOKEN_FACTORY_KEY` yourself, so the key never appears in any conversation.

**S4 · Docs.**

```text
Write README.md from the code and evals/report.md: one-line pitch, a GIF
placeholder for the moods, 60-second install, architecture image, "Where
Nemotron is used" table, "How Token Factory helped", the eval and cascade
tables copied from evals/report.md, the security and privacy model, known
limitations, license. Move depth to docs/ARCHITECTURE.md. Don't invent any
number. Then polish FEEDBACK.md into the submission's feedback section.
```

**S5 · Final passes.** `/simplify` on the biggest modules, then `/code-review`, then `/security-review`, then the `reviewer` subagent against `docs/SPEC.md`. Fix what affects correctness only. Run the clean-account test yourself. Tag `v0.1.0` and let the release workflow publish it.

**Understanding checklist**

- [ ] What does `/goal` do differently from simply asking Claude to finish?
- [ ] Why `onedir` builds, and why download the speech model on first run?
- [ ] What was your attack success rate before and after defences, and what does the remaining gap mean?

---

### After the build: Oct 18–27

Video, write-up and submission follow the Halo plan doc. Claude Code is still useful here, within limits:

- Draft the video script from `docs/SPEC.md` and the demo script; you rewrite it in your own voice.
- Draft the Devpost description from the README.
- Fix bugs you find while recording. Each fix gets its own session, a test, and a PR.
- Never let it invent results, benchmarks or user quotes.

---
## Part 6 — Testing an AI application with Claude

AI apps mix deterministic code (rules, maths, parsing) with non-deterministic model calls. The industry approach is to test each layer differently and keep the slow, costly, non-deterministic tests at the top of the pyramid.

| Layer | What it covers in Halo | Tool | Runs | Cost |
| --- | --- | --- | --- | --- |
| Unit | Mood rules, RRF, policy table, taint propagation, expense SQL, vault round-trip | pytest, Hypothesis | Every commit and in CI | Free, seconds |
| Contract | Python ↔ TypeScript event types; schemas/ up to date | Schema export test, `gen:types` staleness test | Every commit and in CI | Free |
| Component with recorded responses | Model client, cascade, router parsing, worker adapter | pytest-recording (vcrpy) cassettes, recorded `stream-json` | Every commit and in CI | Free after recording |
| UI | Reducer, mood rendering, keyboard handling | Vitest + Testing Library; Playwright screenshots | Every commit (Vitest); on UI changes (screenshots) | Free |
| Live model | Router golden set, Reader extraction | pytest `-m live` | On demand, before merging prompt changes | Token Factory credits |
| Evals | 25 golden tasks, injection suite, cascade ablation | `evals/run_evals.py` | Day 8, then before each release | Credits |
| End-to-end smoke | `halo --demo` scripted run on the demo vault | pytest + subprocess | Before tagging | Credits |

**Rules for tests Claude writes** (these also live in `.claude/rules/tests.md`):

1. **You name the cases.** Claude is good at writing tests for cases you list; on its own it tends to test the happy path.
2. **Red before green.** Every new test must be shown failing first.
3. **Don't mock the unit under test.** Mock the edges (network, clock, filesystem) and nothing else.
4. **Never weaken a test to make it pass.** Say so in every implementation prompt, review test diffs carefully, and use `HALO_LOCK_TESTS=1` when the tests are the specification.
5. **Determinism:** inject the clock, seed randomness, use temperature 0 for parsing calls, and replay recorded responses.
6. **Name tests as behaviours:** `test_expired_item_never_returned`, not `test_retrieve_3`.

---

## Part 7 — Git, CI/CD and release

### 7.1 Branches and pull requests

- `main` is always green. Work happens on feature branches (`feat/memory-retrieval`) or in worktree branches.
- One PR per feature or per day, created by Claude with `gh pr create --fill` or a short description template: what changed, why, how it was tested, screenshots for UI.
- CI must pass before you merge. You merge; Claude doesn't.
- **Optional automated review:** run `/install-github-app` in Claude Code to install the Claude GitHub App. It can add a review workflow that comments on each PR, and lets you mention `@claude` in PR comments. It authenticates with a repository secret (`ANTHROPIC_API_KEY` or a subscription token from `claude setup-token`) and uses your usage. For a solo week, running `/code-review` locally before opening the PR is usually enough.

### 7.2 CI (from Day 1)

The skeleton Claude writes on Day 1 should look like this. Ask it to keep action versions on their current major release.

```yaml
# .github/workflows/ci.yml
name: CI
on:
  push:
    branches: [main]
  pull_request:
jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: astral-sh/setup-uv@v6
      - run: uv python install 3.12
      - run: uv sync --all-extras
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pyright
      - run: uv run pytest -m "not live" -q
  ui:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: ui
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v4
        with:
          node-version: 22
      - run: npm ci
      - run: npm run gen:types && git diff --exit-code src/types
      - run: npx tsc --noEmit
      - run: npx vitest run
  secrets:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
        with:
          fetch-depth: 0
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Live tests and evals don't run in CI on every push: they cost credits and need your Token Factory key. Run them on demand with a `workflow_dispatch` workflow that reads the key from a repository secret.

### 7.3 Release (Day 8)

`release.yml` triggers on tags `v*`, builds on `windows-latest` and `macos-latest`, runs PyInstaller in `onedir` mode, zips the output, and attaches it to a GitHub Release. Ask Claude to write it, push a release-candidate tag (`v0.1.0-rc1`), and watch it with `gh run watch`. Fix until both builds pass, download the Windows build and test it yourself, then tag `v0.1.0`.

### 7.4 Secrets hygiene

- Never paste an API key into a Claude prompt. Scripts load keys from `.env` at runtime.
- `.env` is gitignored before it exists, denied in permissions, and blocked by `protect.py`.
- `gitleaks` runs in CI, including on the full history.
- Deployment secrets (`wrangler secret put`, GitHub repository secrets) are set by **you**, in your own terminal.

---

## Part 8 — When things go wrong

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Claude ignores a rule in CLAUDE.md | The file is too long or the rule is vague | Prune the file; move file-type rules into `.claude/rules/`; mark the single most important rule "IMPORTANT"; if it must never be broken, make it a hook |
| The same mistake after two corrections | The context is full of failed attempts | `/clear`, then one better prompt that includes what you learned |
| Claude says "done" but it doesn't work | No check in the loop | Put the exact commands in the prompt and ask for their output; use `/goal` or a test that encodes "done" |
| Tests were edited to pass | The prompt allowed it | Say "don't modify tests"; start with `HALO_LOCK_TESTS=1`; review test diffs |
| Wrong or invented library API (LangGraph, pywebview, sherpa-onnx) | Training data older than the library | `researcher` subagent with Context7; write the result to `docs/notes/`; spike it |
| Claude wanders into unrelated files | No scope given | Add "Out of scope: …"; use plan mode; name the files |
| Huge, messy diff | Task too big for one pass | Rewind; split into plan steps; "stop after step n" |
| Context fills up mid-feature | Long exploration in the main session | `/compact <focus>`, or `/handoff` → `/clear` → resume from `PROGRESS.md`; push exploration to subagents next time |
| Windows path or shell errors | Git Bash vs PowerShell assumptions | State the shell in `CLAUDE.local.md`; use `uv run` and `pathlib` everywhere; quote paths with spaces |
| Hardware or window code can't be verified | Claude can't see your screen or hear your mic | Fakes and file inputs for tests (`--wav`, `?mock=`); you run the real thing and paste logs or screenshots |
| Two worktree branches conflict at merge | Parallel sessions touched the same files | Parallelise only areas with separate files; merge the contract-touching branch first; ask Claude to resolve conflicts with the tests as the referee |
| You hit plan usage limits | Too many parallel sessions or a heavy model for routine work | Use the faster model for implementation, one session at a time, shorter prompts; spend the time on review, docs or video |

---

## Part 9 — Spending your hours well

**A day, in IST:**

| Time | Activity |
| --- | --- |
| 09:00–09:30 | `/kickoff` in plan mode; adjust and approve the day's tasks |
| 09:30–13:00 | Task block 1: two or three tasks, at most two sessions in parallel |
| 14:00–18:00 | Task block 2 |
| 18:00–19:30 | Review session: reviewer subagent over the day's diff; fix correctness gaps |
| 19:30–21:00 | Dogfood Halo; note bugs as tomorrow's tasks; work through the understanding checklist (Prompt P10) |
| 21:00–21:30 | `/handoff`, merge, push, tag |

**Where the time really goes:** roughly 30% specifying and planning, 40% reviewing and testing, 30% waiting for Claude. Use the waiting time to review the other session's diff, not to open a third session.

**Signs you're falling behind, and what to do:** if a day's Done-when isn't met by 21:00, don't work past midnight. Next morning, cut from the cut list in the Halo plan doc and record it in `docs/DECISIONS.md`. A smaller Halo that works beats a larger one that crashes in the demo.

---

## Part 10 — The reusable kit for future projects

Everything you set up this week is reusable. After Day 8, move the general parts to your user-level folder so every future project starts with them.

| Keep | Where it goes | Why |
| --- | --- | --- |
| Personal working preferences (explain before code, conventional commits, test-first) | `~/.claude/CLAUDE.md` | Applies to every project |
| `reviewer`, `researcher`, `test-writer`, `security-reviewer` subagents | `~/.claude/agents/` | Project-agnostic |
| `/kickoff`, `/handoff`, `/spike` skills | `~/.claude/skills/` | The daily loop works anywhere |
| `format.py` and `protect.py` hooks (made configurable) | A dotfiles repo | Copy into each project's `.claude/hooks/` |
| Templates: SPEC, CONTRACTS, DECISIONS, PROGRESS | A `templates/` folder in your dotfiles | Day 1 of any project in 20 minutes |
| `ci.yml` and `release.yml` | The same templates folder | CI from day one, every time |

When the kit settles, package it as a **Claude Code plugin** (a bundle of skills, subagents, hooks and MCP servers that installs with one command; see the plugins docs). That's a small open-source project in its own right.

**The process you've learned, in one line:** interview → spec → contracts → spikes → vertical slices built test-first → independent review → evals → ship. It works the same for a weekend tool, a client project, or your next hackathon.

---
## Appendix A — Every config file, in full

Copy these as they are on Day 1, then adjust as you learn. Paths are relative to the repo root.

### A.1 `CLAUDE.md`

```markdown
# Halo

Private desktop AI agent with a living character. Python 3.12 core (LangGraph,
FastAPI), React HUD in a pywebview window, memory in an Obsidian vault. All LLM
calls go to NVIDIA Nemotron on Nebius Token Factory.
What we're building: docs/SPEC.md. How: docs/ARCHITECTURE.md.

## Commands
- Install: `uv sync --all-extras` · UI: `cd ui && npm ci`
- Run app: `uv run halo-app` · CLI: `uv run halo "<request>"`
- Tests: `uv run pytest -m "not live" -q` (one file: `uv run pytest tests/memory/test_retrieve.py -q`)
- Live model tests cost credits; ask before running: `uv run pytest -m live -q`
- Lint, format, types: `uv run ruff check . --fix` · `uv run ruff format .` · `uv run pyright`
- UI: `npm run dev` (http://localhost:5173, add `?mock=<path to run .jsonl>`) · `npx vitest run` · `npm run gen:types`
- Evals: `uv run python evals/run_evals.py`

## Architecture rules
- IMPORTANT: docs/CONTRACTS.md and halo/core/contracts.py are frozen. Propose changes; they are applied with /add-event.
- Components talk only through HaloEvent. UI state is derived only from events.
- Character mood is decided in Python (halo/character/mood.py), never in React.
- LLM calls go only through halo/models/client.py, only to Nemotron on Token Factory.
- Untrusted content (web pages, fetched files, Claude Code output) is read only by
  halo/security/reader.py and stays wrapped in Tainted[T].
- Arithmetic on user data (expenses, budgets) happens in SQL or Python, never in a model.
- Notes with `privacy: local` never go into a cloud prompt.

## Workflow
- Changes touching more than 3 files: plan first and wait for approval.
- Tests first for the cases given; show them failing, then passing.
  Never modify a test to make it pass; ask instead.
- Before saying a task is done, run the relevant tests, ruff and pyright and show the output.
- Conventional Commits (`feat(memory): ...`), one logical change per commit.
- Use `gh` for GitHub. Never push to main or force-push.
- Secrets live in .env and are loaded with python-dotenv at runtime. Never print, log or hard-code keys.
- Unsure about a library API (LangGraph, pywebview, sherpa-onnx, claude-agent-sdk)? Check
  docs/notes/ or use the researcher subagent before writing code.
- When compacting, keep: changed files, test commands, open issues, current plan step.

## Environment
- Dev OS is Windows 11 with Git Bash. Code must also run on macOS: pathlib only,
  no shell-specific syntax inside Python.
- Tests never touch the real vault or ~/.halo; use tests/fixtures/.

## State
- Current status and next steps: PROGRESS.md. Decision log: docs/DECISIONS.md.
```

### A.2 `CLAUDE.local.md` (gitignored)

```markdown
# Personal notes (not committed)
- Shell: Git Bash on Windows 11. Repo: C:\Users\<you>\code\halo
- Dev vault (safe to write): C:\Users\<you>\HaloVault-dev
- Real vault: C:\Users\<you>\HaloVault (never write to it from tests)
- Real repo for trying the coding skill: C:\Users\<you>\code\<another-repo>
- When introducing a library I haven't used, explain the concept before the code.
```

### A.3 Path-scoped rules

**`.claude/rules/python.md`**

```markdown
---
paths:
  - "halo/**/*.py"
  - "evals/**/*.py"
---
# Python rules
- Type hints on every function; data crossing module boundaries is a Pydantic v2 model.
- Network and file I/O are async; wrap blocking calls in asyncio.to_thread.
- Config comes from halo/config.py (pydantic-settings), not scattered os.environ reads.
- Use the module logger (logging.getLogger(__name__)); no print().
- Raise specific exceptions; never a bare except.
- subprocess calls take a list of args; never shell=True.
```

**`.claude/rules/ui.md`**

```markdown
---
paths:
  - "ui/**/*.{ts,tsx}"
---
# UI rules
- Event types come from ui/src/types (generated). Never edit them; run npm run gen:types.
- All state lives in the zustand store, produced by the event reducer. Components are pure.
- Animation: Framer Motion. Mascot shapes: Rough.js. No other animation libraries.
- Styling: Tailwind only.
- After any visual change, screenshot it with Playwright at /moods or with ?mock= and compare.
```

**`.claude/rules/tests.md`**

```markdown
---
paths:
  - "tests/**/*.py"
  - "ui/**/*.test.{ts,tsx}"
---
# Test rules
- Test names describe behaviour: test_expired_item_never_returned.
- Mock only the edges (network, clock, filesystem), never the unit under test.
- Tests that call a real model are marked @pytest.mark.live.
- Use tests/fixtures/; never the real vault or ~/.halo.
- Cassettes must filter the Authorization header.
```

**`.claude/rules/security.md`**

```markdown
---
paths:
  - "halo/security/**"
  - "halo/tools/**"
  - "halo/models/**"
---
# Security rules
- Any value derived from untrusted content is Tainted[T] until the Reader's schema has validated it,
  and it stays Tainted afterwards.
- Every tool declares its risk level and which arguments may accept tainted values.
- High-risk tools (delete files, send messages, spend money, git merge or push) always ask;
  they can never be set to "always allow".
- Every new tool gets a test in tests/security/.
```

### A.4 `.claude/settings.json`

```json
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "permissions": {
    "allow": [
      "Bash(uv run pytest *)",
      "Bash(uv run ruff *)",
      "Bash(uv run pyright *)",
      "Bash(uv run halo *)",
      "Bash(uv run python spikes/*)",
      "Bash(uv run python evals/*)",
      "Bash(uv run python -m halo.*)",
      "Bash(uv sync *)",
      "Bash(uv add *)",
      "Bash(npm run *)",
      "Bash(npm ci)",
      "Bash(npx vitest *)",
      "Bash(npx tsc *)",
      "Bash(git status *)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(git add *)",
      "Bash(git commit *)",
      "Bash(git switch *)",
      "Bash(git worktree *)",
      "Bash(gh pr *)",
      "Bash(gh run *)",
      "WebFetch(domain:docs.langchain.com)",
      "WebFetch(domain:docs.pydantic.dev)",
      "WebFetch(domain:fastapi.tiangolo.com)",
      "WebFetch(domain:pywebview.flowrl.com)",
      "WebFetch(domain:k2-fsa.github.io)",
      "WebFetch(domain:code.claude.com)"
    ],
    "ask": [
      "Bash(git push *)",
      "Bash(git merge *)",
      "Bash(uv remove *)",
      "Bash(npm install *)"
    ],
    "deny": [
      "Read(./.env)",
      "Read(./.env.local)",
      "Bash(git push --force *)",
      "Bash(git push -f *)",
      "Bash(git reset --hard *)",
      "Bash(rm -rf *)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "uv run --no-project python \"$CLAUDE_PROJECT_DIR/.claude/hooks/protect.py\""
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "uv run --no-project python \"$CLAUDE_PROJECT_DIR/.claude/hooks/format.py\""
          }
        ]
      }
    ]
  }
}
```

Add documentation domains to the WebFetch allowlist as you need them, including the Nebius Token Factory docs.

### A.5 `.claude/hooks/protect.py`

```python
"""PreToolUse hook: block edits to protected files.

Claude Code sends the tool call as JSON on stdin. Exit code 2 blocks the edit,
and the message on stderr tells Claude why.
"""
import json
import os
import sys
from pathlib import PurePosixPath

data = json.load(sys.stdin)
raw = data.get("tool_input", {}).get("file_path", "")
path = PurePosixPath(raw.replace("\\", "/"))
posix = path.as_posix()


def block(reason: str) -> None:
    print(reason, file=sys.stderr)
    sys.exit(2)


if path.name.startswith(".env") and path.name != ".env.example":
    block(f"{path.name} holds secrets and is protected. Ask the user to edit it.")

if path.name in {"LICENSE", "uv.lock", "package-lock.json"}:
    block(f"{path.name} is protected. Lockfiles change only via uv or npm; LICENSE never changes.")

frozen = ("docs/CONTRACTS.md", "halo/core/contracts.py")
if posix.endswith(frozen) and os.environ.get("HALO_CONTRACT_EDIT") != "1":
    block(
        "Contracts are frozen. Propose the change to the user; it is applied with "
        "/add-event in a session started with HALO_CONTRACT_EDIT=1."
    )

is_test = "tests" in path.parts or posix.endswith((".test.ts", ".test.tsx"))
if os.environ.get("HALO_LOCK_TESTS") == "1" and is_test:
    block("Tests are locked for this session (HALO_LOCK_TESTS=1). Make them pass without editing them.")

sys.exit(0)
```

### A.6 `.claude/hooks/format.py`

```python
"""PostToolUse hook: format and lint the file Claude just edited.

Lint errors that can't be auto-fixed go to stderr with exit code 2, which
Claude Code shows to Claude so it fixes them in the same turn.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path")
if not file_path:
    sys.exit(0)

path = Path(file_path)
root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def run(cmd: list[str], cwd: Path = root) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


if path.suffix == ".py":
    run(["uv", "run", "ruff", "format", str(path)])
    result = run(["uv", "run", "ruff", "check", "--fix", str(path)])
    if result.returncode != 0:
        print(f"ruff found problems in {path.name} that need a manual fix:\n{result.stdout[-3000:]}",
              file=sys.stderr)
        sys.exit(2)
elif path.suffix in {".ts", ".tsx", ".css"} and "ui" in path.parts:
    npx = shutil.which("npx")
    if npx:
        run([npx, "prettier", "--write", str(path)], cwd=root / "ui")

sys.exit(0)
```

To start a session with one of the protections lifted, set the variable before launching: `HALO_CONTRACT_EDIT=1 claude` in Git Bash, or `$env:HALO_CONTRACT_EDIT=1; claude` in PowerShell.

### A.7 Subagents (`.claude/agents/`)

Read-only subagents use `disallowedTools` instead of a `tools` list, so they keep access to MCP tools (Context7, Playwright) without being able to edit files.

**`researcher.md`**

```markdown
---
name: researcher
description: Looks up CURRENT documentation and real usage for a library or API (LangGraph, pywebview, sherpa-onnx, claude-agent-sdk, Nebius Token Factory, Tavily). Use before writing code against a library whose API may have changed. Read-only.
disallowedTools: Edit, Write, NotebookEdit
model: sonnet
---
You are a documentation researcher for the Halo project.

1. Find the installed version in pyproject.toml, uv.lock or ui/package.json.
2. Look the answer up in Context7 or the official docs for THAT version. Never answer from memory alone.
3. For each question return: a minimal working example, the version it applies to, the source URL,
   and any gotchas (deprecated names, Windows-specific behaviour).
4. If you can't find it, say "not found" and what you tried. Never guess an API.
Keep the report under 400 words.
```

**`test-writer.md`**

```markdown
---
name: test-writer
description: Writes failing tests for a listed set of cases before implementation. Use when starting any feature or bug fix.
tools: Read, Grep, Glob, Edit, Write, Bash
model: sonnet
---
You write tests for Halo, before the implementation exists.

- Write exactly the cases you're given, plus at most two edge cases you think are missing (label them).
- Test names describe behaviour. Use fixtures from tests/fixtures/.
- Mock only network, clock and filesystem edges, never the unit under test.
- Mark tests that call a real model with @pytest.mark.live.
- Run the tests and confirm they fail for the RIGHT reason (missing behaviour, not an import error).
- Report: files created, each test name, and the failure output.
```

**`reviewer.md`**

```markdown
---
name: reviewer
description: Independent review of a diff against the plan and spec. Use after a feature is implemented and before merging.
tools: Read, Grep, Glob, Bash
model: opus
---
You review Halo changes with fresh eyes. You did not write this code.

Inputs: the diff (run `git diff main...HEAD` unless told otherwise) and the reference docs named in
the request (plan, spec, docs/CONTRACTS.md).

Check:
1. Every stated requirement and acceptance criterion is implemented.
2. Every listed edge case has a test, and the tests would fail if the behaviour broke.
3. Nothing outside the stated scope changed; contracts were not edited directly.
4. Errors are handled, not swallowed; no secrets, prints or debug leftovers.

Report:
- BLOCKING: gaps that affect correctness or a stated requirement, each with file:line, why it matters,
  and a suggested fix.
- NON-BLOCKING: at most 3 items.
Do not report style preferences. If nothing is blocking, say so plainly.
```

**`security-reviewer.md`**

```markdown
---
name: security-reviewer
description: Security review of Halo's agent paths - untrusted input reaching tools, secret leaks, policy gaps. Use after changes to halo/security, halo/tools, halo/models or any new tool.
tools: Read, Grep, Glob, Bash
model: opus
---
You are a security engineer reviewing an AI agent that reads untrusted content and can act on a
user's computer. Use docs/THREAT_MODEL.md as the reference.

Look for:
- Paths where content from web pages, fetched files, memory from web sources or Claude Code output
  reaches a tool, a prompt or a file write without passing the Reader and staying Tainted.
- Tools missing a risk level, or high-risk tools that can be set to "always allow".
- Text from privacy: local notes that could reach a cloud prompt.
- Secrets in code, logs, cassettes, fixtures or error messages.
- shell=True, unsanitised paths (path traversal in vault or worktree paths), unsafe deserialisation.

Report only exploitable findings: file:line, the concrete attack, its impact, and the fix.
```

**`ui-critic.md`**

```markdown
---
name: ui-critic
description: Visual review of the Halo HUD in a real browser against the design notes. Use after UI changes.
disallowedTools: Edit, Write, NotebookEdit
model: sonnet
---
You review Halo's HUD visually.

1. Open the page you're given (default http://localhost:5173/moods) with the Playwright tools and
   take screenshots, including the 260x44 collapsed bar size.
2. Compare against the mood table and HUD layout in docs/ARCHITECTURE.md: face, ring colour,
   accessory, sizes, text truncation, contrast, keyboard focus.
3. List differences in priority order with a screenshot reference for each. Don't fix anything.
```

### A.8 Skills (`.claude/skills/<name>/SKILL.md`)

**`kickoff/SKILL.md`**

```markdown
---
name: kickoff
description: Start-of-day planning for Halo. Reads progress and today's plan, proposes the day's tasks.
disable-model-invocation: true
---
Day number: $ARGUMENTS (if empty, infer it from docs/PLAN.md and PROGRESS.md).

1. Read PROGRESS.md, today's section of docs/PLAN.md, and the last 5 entries of docs/DECISIONS.md.
   Run `git status` and `git log --oneline -10`.
2. List what carries over from yesterday: unfinished work and known issues.
3. Propose today's tasks in order. For each: goal, files likely touched, the check that proves it's done,
   and whether it can run in a parallel worktree (only if it touches different files and its contracts exist).
4. Flag risks to today's "Done when" and name what to cut first if time runs short.
5. Don't write code. Wait for my approval.
```

Use it in plan mode: press `Shift+Tab` until plan mode is on, then run `/kickoff 3`.

**`handoff/SKILL.md`**

```markdown
---
name: handoff
description: End-of-session handoff. Runs checks, updates PROGRESS.md and DECISIONS.md, commits.
disable-model-invocation: true
---
1. Run `uv run pytest -m "not live" -q`, `uv run ruff check .`, `uv run pyright`, and `npx vitest run`
   in ui/ if UI files changed. Report the results; don't start new fixes now.
2. Rewrite PROGRESS.md (under 60 lines): Done this session, In progress (with the exact next step),
   Next, Known issues, How to run. Replace stale content; don't append forever.
3. Append each decision made this session to docs/DECISIONS.md:
   `YYYY-MM-DD — decision — why — rejected alternative`.
4. Commit uncommitted work as separate logical conventional commits, then the progress update as
   `chore(progress): ...`. Show `git log --oneline -5`.
5. Print a 3-line summary for my daily log.
```

**`new-halo-skill/SKILL.md`**

```markdown
---
name: new-halo-skill
description: Scaffold a new Halo skill with manifest, implementation stub, registry entry, router examples and failing tests. Use whenever a new skill is added to Halo.
---
Create a Halo skill named $ARGUMENTS, following the structure of skills/app_open/:

1. skills/$ARGUMENTS/SKILL.md with frontmatter (name, description, tools, risk: low|medium|high)
   and a short "When to use" section.
2. skills/$ARGUMENTS/skill.py implementing the Skill protocol from halo/core/contracts.py
   (`async def run(ctx, args)`), emitting step and tool events through ctx.
3. Register it in skills/registry.py; add 3 routing examples to evals/router_golden.yaml.
4. tests/skills/test_$ARGUMENTS.py with failing tests for the happy path, invalid args, and the
   policy decision for each tool it uses.
5. Run the new tests and show them failing. Don't implement the logic yet.
```

**`add-event/SKILL.md`**

```markdown
---
name: add-event
description: Change the frozen contracts safely - add or modify a HaloEvent type or shared model and update every consumer together.
disable-model-invocation: true
---
Requested change: $ARGUMENTS

Only continue if this session was started with HALO_CONTRACT_EDIT=1. If not, stop and tell me how to restart.

1. Explain the change and list every consumer (search for the type name in halo/, ui/src/, tests/, evals/).
2. Wait for my approval.
3. Update halo/core/contracts.py and docs/CONTRACTS.md.
4. Run `uv run python -m halo.core.export_schemas`, then `npm run gen:types` in ui/.
5. Update the reducer, the mood rules (if mood is affected) and the recorder as needed.
6. Update tests on both sides; run the full Python and UI suites and show the results.
7. Add a line to docs/DECISIONS.md.
```

**`spike/SKILL.md`**

```markdown
---
name: spike
description: Run a time-boxed technical experiment that answers one question with a number, and record the result.
---
Question: $ARGUMENTS

1. Restate the question, the number(s) that will answer it, and the decision each outcome leads to.
2. Write the smallest script that measures it in spikes/<short-name>.py. Load secrets with
   python-dotenv; never print them.
3. Run it. If it needs my hardware (microphone, screen), tell me exactly how to run it and wait for my output.
4. Append to spikes/RESULTS.md: date, question, method, result with numbers, decision.
5. Spike code is throwaway. Never import it from halo/.
```

**`eval/SKILL.md`**

```markdown
---
name: eval
description: Run Halo's eval suite and summarise changes against the previous report.
disable-model-invocation: true
---
1. Copy evals/report.md to evals/report.prev.md if it exists.
2. Run `uv run python evals/run_evals.py $ARGUMENTS`. It costs Token Factory credits: ask me first if
   more than 25 live tasks will run.
3. Summarise: overall golden-task success, per-category change vs report.prev.md, attack success with
   defences off and on, cascade table changes, and the cost of this run.
4. For each regression: the task, the failing check, and the most likely cause among commits since the
   previous report.
```

### A.9 Templates and small files

**`PROGRESS.md`**

```markdown
# Progress
_Last updated: YYYY-MM-DD HH:MM by /handoff_

## Done
-

## In progress
- <task> — next step: <exact next action>

## Next
-

## Known issues
-

## How to run
- `uv sync --all-extras && cd ui && npm ci`
- `uv run halo-app`
```

**`docs/DECISIONS.md`**

```markdown
# Decisions
One line each: date — decision — why — rejected alternative.

- 2026-10-10 — pywebview + React for the HUD — one Python process, packages with PyInstaller — Electron (second runtime, larger build)
```

**`.worktreeinclude`**

```text
.env
```

---

## Appendix B — Cheat sheet

| Action | How |
| --- | --- |
| Cycle permission modes, including plan mode | `Shift+Tab` |
| Enter plan mode with a task | `/plan <task>` |
| Edit Claude's plan in your editor | `Ctrl+G` |
| Stop Claude mid-action | `Esc` |
| Rewind code and/or conversation | `Esc Esc` or `/rewind` |
| New conversation, empty context | `/clear` |
| Free context, keep a summary | `/compact <what to keep>` |
| See what's using context | `/context` |
| Side question that stays out of context | `/btw <question>` |
| Name, continue, resume sessions | `/rename <name>` · `claude --continue` · `claude --resume` |
| Switch model and effort | `/model` (arrows adjust effort) |
| Usage and cost | `/usage` |
| Reference a file in a prompt | `@path/to/file` |
| Give Claude an image | Paste or drag it into the prompt |
| Parallel session in its own worktree | `claude --worktree <name>` |
| Non-interactive run with streamed events | `claude -p "<prompt>" --output-format stream-json --verbose` |
| Generate a starter CLAUDE.md | `/init` |
| Edit CLAUDE.md files, view auto memory | `/memory` |
| View hooks · MCP servers · permissions · skills | `/hooks` · `/mcp` · `/permissions` · `/skills` |
| Bug-finding review of the current diff | `/code-review` |
| Cleanup review (reuse, simplification) | `/simplify` |
| Security review of the branch diff | `/security-review` |
| Keep working until a condition holds | `/goal <condition>` |
| Run the app and confirm a change works | `/verify` |
| Explanatory output while learning | `/config` → output style |
| Diagnose installation and settings | `claude doctor` (terminal) or `/doctor` (in a session) |
| Status line with context and cost | `/statusline <description>` |
| Install the Claude GitHub App and workflows | `/install-github-app` |

---

## Appendix C — Sources

- Best practices for Claude Code: https://code.claude.com/docs/en/best-practices
- Common workflows: https://code.claude.com/docs/en/common-workflows
- How Claude remembers your project (CLAUDE.md, rules): https://code.claude.com/docs/en/memory
- Commands: https://code.claude.com/docs/en/commands
- Permission modes: https://code.claude.com/docs/en/permission-modes
- Configure permissions: https://code.claude.com/docs/en/permissions
- Hooks guide: https://code.claude.com/docs/en/hooks-guide · reference: https://code.claude.com/docs/en/hooks
- Subagents: https://code.claude.com/docs/en/sub-agents
- Skills: https://code.claude.com/docs/en/skills
- MCP: https://code.claude.com/docs/en/mcp
- Worktrees: https://code.claude.com/docs/en/worktrees
- Checkpointing: https://code.claude.com/docs/en/checkpointing
- Run Claude Code programmatically (`claude -p`): https://code.claude.com/docs/en/headless
- Agent SDK (Python): https://code.claude.com/docs/en/agent-sdk/python
- GitHub Actions: https://code.claude.com/docs/en/github-actions
- Advanced setup (Windows): https://code.claude.com/docs/en/setup
- Manage costs and context: https://code.claude.com/docs/en/costs
