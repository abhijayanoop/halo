---
name: memory.recall
description: Answer from what the user told Halo earlier, with links to the notes.
tools: [vault_read]
risk: low
---
## When to use

The user asks what they told Halo before ("what did I pick for the HUD window?").
Halo searches the vault and answers with the matching facts, each with an
`obsidian://` link to its note. If nothing matches it says it doesn't know.

It reads the vault on this computer and never calls a model, so it may show
facts from `privacy: local` notes on the user's own screen. Facts that came from
the web, a tool or an agent are marked as hints.
