# Decisions
One line each: date — decision — why — rejected alternative.

- 2026-10-10 — pywebview + React for the HUD — one Python process, packages with PyInstaller — Electron (second runtime, larger build)
- 2026-10-10 — GitHub repo created under github.com/abhijayanoop, public — that's the account the user wants this work attributed to — the already-active `abhijayanoop-elcarreira` CLI session account
- 2026-10-10 — `Skill` protocol modeled as a `run(self, ctx, args)` method, not `__call__` — matches the spec's literal wording and still structurally satisfies a bare module-level `async def run(ctx, args)` — a `__call__`-based Protocol
- 2026-10-10 — `MemoryItem.privacy` is an explicit field, copied from the destination note's frontmatter at write time — lets the cloud-prompt raising check in `models/client.py` enforce the privacy rule on `MemoryItem`s alone, without reaching into the vault — inferring privacy only from the note at read time
- 2026-10-10 — pywebview confirmed as the HUD host (frameless, always-on-top, JS-driven resize all verified on Windows), no fallback needed — n/a — square frameless window / Electron
- 2026-10-10 — claude-agent-sdk confirmed for the Day 4 coding worker (streaming and `can_use_tool` both verified against a scratch repo; reuses the existing `claude` CLI login) — n/a — plain `claude -p --output-format stream-json` CLI invocation
- 2026-10-10 — Voice (ASR) ships as a secondary input for v0.1; typing/push-to-talk stays primary — Parakeet CTC 110M int8 decodes in <200ms but is inaccurate on live mic audio; the matching transducer variant fails to load (sherpa-onnx version incompatibility), and Wispr Flow's MCP server doesn't do speech-to-text at all (and would break the local-only voice constraint anyway) — switching ASR model/vendor now to chase accuracy
- 2026-10-10 — CI's secret scan installs the gitleaks CLI binary directly rather than using `gitleaks/gitleaks-action` — that action is commercially licensed for orgs and is being deprecated (Node 20 runner removal) — `gitleaks/gitleaks-action`
- 2026-10-10 — `docs/` excluded from ruff's lint/format scope — it's reference/planning markdown with illustrative code snippets, not shipped code — reformatting the playbook/architecture docs' embedded snippets to satisfy ruff
