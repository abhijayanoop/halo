---
name: app.open
description: Open an allowlisted desktop app by name or alias.
tools: [launch_app]
risk: low
---
## When to use

The user asks to open, launch or start an app ("open VS Code"). Apps on the
allowlist in `config.toml` open straight away. Any other app is never launched
by this skill: it returns `needs_approval` so the executor can ask first
(medium risk).
