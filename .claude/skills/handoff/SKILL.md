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
