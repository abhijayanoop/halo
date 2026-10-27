---
name: code.task
description: "Work on code in one of the user's projects: explain it, plan a change, or make the change in a separate copy of the repo."
tools: [repo_map, git_worktree, claude_code, test_run]
risk: low
---
## When to use

The user asks to explain, plan or change code in a project ("add rate limiting to the
webhook endpoint"). `args`: `task` (what to do), `mode` (`explain`, `plan` or `implement`,
default `implement`) and `project` (the name of a note in the vault's `Projects` folder).

## How it stays safe

- The project is chosen by its note name only. Its folder, test command and branch come from
  the project note, never from the request, the model or an edit on the card.
- `explain` and `plan` answer from a map of the repo and change nothing.
- `implement` writes a brief and stops at the brief card. Nothing is created and nothing
  runs until the user approves it. The work happens in a separate git worktree on its own
  branch, so the user's checkout and main branch are untouched.
- Halo runs the project's tests itself and an Ultra review grades the change against the
  brief; both appear on the result card. The worker's own report is never trusted.
- Merge is a button on the result card, never an automatic step and never remembered
  between cards. It is a local merge and never pushes.
- The skill's risk is low because the brief card, not a generic yes, is the approval. No
  argument accepts text derived from untrusted content.
