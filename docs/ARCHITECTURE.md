## Architecture and stack

One Python process runs everything except the model calls: a LangGraph agent, a FastAPI server streaming typed events, and a pywebview window showing the React HUD. Only Nemotron inference goes to Nebius Token Factory, and only the context the policy engine allows.

&#91;embedded content: Halo architecture · everything local except Nemotron inference\]

Every model call and tool call passes through the policy engine. The flight recorder (not drawn) saves every event the HUD shows.

**Stack:** Python 3.12 with `uv`, `ruff`, `pyright`, `pytest` · LangGraph + `langgraph-checkpoint-sqlite` · Pydantic v2 (+ `instructor` if needed) · `openai` SDK pointed at Token Factory · FastAPI + WebSocket · pywebview + React/Vite/Tailwind + Framer Motion · sherpa-onnx (Nemotron ASR or Parakeet) + `sounddevice` + `pynput` · Obsidian vault + `python-frontmatter` + `watchdog` · SQLite FTS5 + `sqlite-vec` + SQLModel · `mcp` SDK + FastMCP · `tavily-python` + Playwright · `claude-agent-sdk` + GitPython · APScheduler · OpenTelemetry + Arize Phoenix · PyInstaller + GitHub Actions.

| Model (all on Token Factory except ASR) | Job in Halo | Why this model |
| --- | --- | --- |
| Nemotron 3 Nano | Router, expense parser, memory extractor, quarantined Reader, HUD status lines | Fastest and cheapest; called most often |
| Nemotron 3 Super | Planner, coding task briefs | 1M-token context holds a repo map plus project notes |
| Nemotron 3 Ultra | Code review, trip synthesis, eval judge | Hardest reasoning; called rarely |
| Nemotron 3 Nano Omni | Receipts and screenshots to structured data | Image input |
| Nemotron ASR (local, sherpa-onnx) | Voice to text | Private, offline, no API cost |

**Escalation rule:** Nano answers first with a confidence score. Low confidence or a failed Pydantic validation sends the call to Super, and every hop is logged with its cost and latency.

**The event contract.** Everything the HUD shows and the flight recorder saves is one typed event. Define it on Day 1 and never break it:

```python
class HaloEvent(BaseModel):
    id: str                 # ulid
    run_id: str             # one user request
    ts: datetime
    type: Literal[
        "run.started", "run.finished", "run.failed",
        "step.started", "step.finished",
        "agent.spawned", "agent.finished",
        "tool.called", "tool.result",
        "approval.requested", "approval.resolved",
        "memory.proposed", "memory.saved", "memory.forgotten",
        "egress.sent", "cost.updated",
        "policy.blocked", "voice.listening", "voice.heard",
        "mood",               # character state, derived on the backend
    ]
    agent_id: str | None = None
    parent_agent_id: str | None = None
    title: str              # short human text, e.g. "Searching hotels in Anjuna"
    payload: dict = {}
```

## The character and the HUD

Halo's face is the HUD's main signal: one glance tells you whether it is idle, thinking, working, waiting on you or blocking something. The backend decides the mood from events; the frontend only draws it. The character always tells the truth about what the agent is doing.

**The doodle.** A soft, slightly lopsided bean with two oval eyes, a small mouth, and a halo ring floating above its head.

- **Hand-drawn look:** draw every shape with Rough.js, which turns SVG paths into sketchy pencil lines.
- **Boiling line:** while Halo is working, re-draw the outline with a new Rough.js seed about 8 times a second, so the line shimmers like a hand-drawn cartoon. It stays still when idle or asleep, which makes "busy" readable from across the room.
- **Layers:** body · eyes · mouth · halo ring (colour and motion carry state) · one accessory slot (Zzz, magnifying glass, pencil, raised hand, shield, sparkles, sweat drop) · one mini-halo orbiting per running sub-agent.
- **Always alive:** a random blink every 3–6 s and gentle breathing (scale 1.00 to 1.03 over 3 s), animated with Framer Motion springs.

&#91;embedded content: Halo mood sheet · 8 of the 13 moods\]

A first sketch to build from: keep the bean, the oval eyes and the floating ring, and give each mood one accessory at most. Ring colours in this sketch are placeholders; the app palette is set on Day 2.

**Moods.** `halo/character/mood.py` maps events to moods with fixed rules, no model involved. Each mood stays on screen for at least 700 ms so the face never flickers.

| Mood | Triggered by | Face, halo, accessory | Example status line |
| --- | --- | --- | --- |
| Asleep | No activity for 10 min | Eyes closed, slow breathing, Zzz, halo dim grey | "Zzz · Ctrl+Space to wake me" |
| Waking | App start or hotkey after sleep | Squash-and-stretch, eyes pop open, halo lights up | "Morning. Two things from yesterday." |
| Idle | Ready, nothing running | Slow blinks, gentle float | "Ready" |
| Listening | `voice.listening` | Eyes wide, small "o" mouth, halo pulses with mic volume | "Listening…" |
| Thinking | Router or planner step | Eyes up and left, three thought dots, halo spins slowly | "Working out a plan" |
| Focused | `tool.called`, coding worker running | Squint, tongue tip out, halo becomes a progress ring | "Editing webhook.py" |
| Delegating | `agent.spawned` | Mini-halos split off and orbit, one per sub-agent | "Sent 4 helpers out" |
| Careful | Quarantined Reader opens untrusted content | Magnifying glass, one eyebrow raised | "Reading a web page, carefully" |
| Remembering | `memory.proposed` / `memory.saved` | Pencil and notepad, small nod | "Noted: you prefer Electron" |
| Asking | `approval.requested` | Raised hand, looks straight at you, halo pulses amber, bar auto-expands | "Can I run npm test?" |
| Guarding | `policy.blocked` | Shield up, frown, halo red | "Blocked a hidden instruction" |
| Delighted | `run.finished` with success (2 s, then Idle) | Happy ^ ^ eyes, bounce, sparkles | "Tests pass. Ready to merge." |
| Confused | `run.failed` or repeated validation retries | Spiral eyes, sweat drop | "That didn't work. Here's why." |

**Priority when events overlap:** Asking > Guarding > Confused > Listening > Delegating > Focused > Careful > Thinking > Remembering > Delighted > Idle > Asleep. A permission request always wins.

**Status lines.** Nemotron Nano writes each line from the event title and the active skill. A template is the fallback when Nano is slow (over 400 ms) or the line fails validation. Rules for Halo's voice:

- At most 7 words, present tense, specific nouns ("Comparing 14 hotels in Anjuna", never "Processing…").
- Warm and a little playful when things go well. Plain and serious for permissions, errors and money.
- Uses your name only when greeting. No emoji, no exclamation marks in errors.

**HUD layout and behaviour:**

| State | Size and place | What it shows | How you get there |
| --- | --- | --- | --- |
| Collapsed bar | 260 × 44 px, top centre, 8 px from the edge | Mascot (36 px), one status line, step progress (3/7), one dot per running sub-agent | Default; Esc from any other state |
| Permission card | Grows to 380 × 140 px in place | What and why, risk level, the exact command or a diff summary; Allow once (Enter), Deny (Esc), Always for this task | Opens on its own on `approval.requested` |
| Expanded panel | Drops down to 420 × 600 px | Header with a bigger mascot and Pause/Stop. Tabs: Now (timeline and agent tree), Approvals, Memory (proposed memories), Ledger (egress and ₹ cost), History (replay past runs). Text box and mic at the bottom. | Click the bar, or Ctrl+Space then speak |

&#91;embedded content: HUD states · collapsed bar, permission card, alert banner, expanded panel\]

The collapsed bar is all you see most of the day; a permission request or an alert grows it in place, and a click opens the full panel.

Shortcuts: **Ctrl+Space** wakes Halo and holds to talk · **Ctrl+Shift+.** pauses the current run · **Esc** collapses. Drag the bar to move it along the top edge. High-risk actions (deleting files, sending messages, spending money, `git push`) can never be set to "Always".
