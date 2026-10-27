---
name: app.open
description: Open an allowlisted desktop app by name or alias.
tools: [launch_app]
risk: low
---
## When to use
The user asks to open, launch or start an app ("open VS Code"). Apps on the
allowlist in `config.toml` open straight away. Any other app is launched only
after the user approves it: without the executor's `approved` flag the skill
returns `needs_approval` (medium risk). The flag is set by the executor, never
by `args`. An approved name must be a plain app name (letters, digits, space,
`.`, `_`, `-`) and is launched as an argument list, never through a shell.
