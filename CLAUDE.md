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
