# Contracts

The shared types every Halo component talks through, defined in `halo/core/contracts.py` (Pydantic v2). **Frozen:** propose a change, then apply it with the `/add-event` skill — never edit this file or `contracts.py` directly. JSON Schema for every model below is exported to `schemas/` by `python -m halo.core.export_schemas`; a test fails if `schemas/` drifts from the code.

### HaloEvent
The one typed event every component emits and the HUD/flight-recorder consume. Carries `run_id`, a timestamp, one of 20 fixed `type` values, optional agent linkage, a short human `title`, and a free-form `payload`. All inter-component communication and all UI state derive from this.

### Intent
The router's output: which of the 10 v0.1 skills, with what arguments, and a confidence score. Confidence below 0.7 (or a validation failure) is the signal that escalates from Nano to Super.

### Step
One tool call inside a `Plan`: a tool name, its arguments, and a risk tier (`low`/`medium`/`high`).

### Plan
The planner's (Super's) multi-step output for skills that need one, scoped to a `run_id` and the `skill` it serves, with a short `rationale` and an ordered list of `Step`s. Single-step skills skip this entirely.

### TaskBrief
The contract for a coding work session: `goal`, `acceptance_criteria`, `likely_files`, `test_cmd`, `constraints`, `out_of_scope`. Shown in the approval card, editable there before you approve it, and what the reviewer later grades the diff against.

### Review
A verdict against a `TaskBrief`'s acceptance criteria — `result` (`pass`/`concerns`), a required plain-language `summary` (so an infra failure like "test command timed out" is always expressed, not just itemized review comments), and a list of `issues`. Reused unchanged as the eval judge's verdict shape.

### MemoryItem
A stored, provenanced memory: the `fact`, its `source` and `trust`, when it was created and (optionally) expires, its Obsidian `block_id` and `note_path`, whether it's `superseded`, and `privacy` (`shared`/`local`). **`privacy` is set by the vault/skill layer from the destination note's frontmatter at write time — it is not inferred or looked up later.** This is what lets `halo/models/client.py` enforce "no `privacy: local` content in a cloud prompt" by inspecting `MemoryItem`s alone, without reaching back into the vault.

### MemoryCandidate
An extracted memory proposal awaiting approval (`fact`, `subject`, `source`, `trust`). Not yet tied to a note, so it has no `privacy` — that's decided once a skill picks the destination note and the candidate becomes a `MemoryItem`.

### Expense
A logged expense: `amount` (as `Decimal`, never `float`, to avoid rounding drift before SQL computes totals), `currency`, `category`, `merchant`, `date`, an optional `note`, and an optional `confidence` (populated only on the Nano-Omni receipt-photo path). Arithmetic on these happens in SQL — never in a model.

### ApprovalRequest
The payload behind an `approval.requested` event and the HUD's permission card: a human-readable `action`, the exact `detail` (command or diff summary), and a `risk` tier. **"High risk can never be satisfied by an always-grant" is enforced in `halo/security/policy.py`, not here** — the request and the eventual decision are separate payloads that only meet at the policy engine, so there's nothing to validate against on this model alone.

### ApprovalDecision
The `POST /approve` body that resumes a paused LangGraph node via `Command(resume=decision)`: one field, `grant` (`allow_once`/`deny`/`always_for_task`). `always_for_task` grants are session-scoped only, enforced by the policy engine — never persisted to disk.

### SkillManifest
Parsed from a skill's `SKILL.md` frontmatter: `name`, `description`, `tools`, `risk`.

### RunContext / Skill
`RunContext` is the minimal interface a running skill gets: a `run_id` and an `emit(event)` method to publish `HaloEvent`s as it works. `Skill` is a `Protocol` with `async def run(self, ctx, args)` — a skill module's top-level `async def run(ctx, args)` function satisfies it directly, since a module-level function isn't bound like a class method.
