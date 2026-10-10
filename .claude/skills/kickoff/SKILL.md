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
