---
name: memory.remember
description: Keep a fact the user asked Halo to remember, in their Obsidian vault.
tools: [vault_write]
risk: low
---
## When to use

The user says "remember that ..." or states a fact they want kept. The fact is
written straight away, as one line with `src:: you`, to `Profile.md` or to the
note named in `note`. The user said it themselves, so it is high trust. Read the
line back in Obsidian; delete it there and Halo forgets it.

The note must be a `.md` file inside the vault. Anything else is refused.
