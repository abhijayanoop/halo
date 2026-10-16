---
name: memory.forget
description: Delete what Halo remembers about something, after the user approves.
tools: [vault_delete]
risk: medium
---
## When to use

The user says "forget ..." about something Halo remembers. Medium risk: the
permission card shows what will be deleted, and the skill does nothing until the
executor has set `approved`. It is never an "always for this task" grant.

Only lines that contain every meaningful word of the query are deleted, at most
three, so a vague request deletes nothing. Each deleted line is reported with a
`memory.forgotten` event.
