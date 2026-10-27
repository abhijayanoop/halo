---
name: work.start
description: "Start a work session: say where the user stopped and propose up to three things to pick up."
tools: [vault_read]
risk: low
---
## When to use

The user says "let's get to work" or "let's get started" (the router sends these here
directly, with no model call). Halo reads the project notes in the vault's `Projects`
folder and today's journal (`Journal/YYYY-MM-DD.md`), then answers with where the user
stopped and up to three proposals: unfinished work from a project's `last_stop`, today's
open journal checkboxes (`- [ ] ...`), then open checkboxes in the project notes. Each
proposal carries the request that starts it.

## How it stays safe

- It calls no model: the answer is built from the user's own notes, so nothing in a note
  can reach a prompt and the answer is instant.
- It reads only notes inside the vault (a link out of it is refused) and never the Inbox of
  proposed memories. It takes no arguments and writes nothing.
