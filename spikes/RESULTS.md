# Spike results

One entry per spike: date, question, method, result with numbers, decision.

---

## 2026-10-10 — Local ASR latency (sherpa-onnx, Parakeet CTC 110M int8)

**Question.** Can a local sherpa-onnx ASR model transcribe speech fully offline, with decode latency after speech ends under 1 second (the Day 0 threshold for choosing hands-free voice over push-to-talk-only)?

**Method.** Downloaded `sherpa-onnx-nemo-parakeet_tdt_ctc_110m-en-36000-int8` (NVIDIA Parakeet TDT CTC, 110M params, int8-quantized) from the k2-fsa/sherpa-onnx `asr-models` GitHub release into `spikes/models/parakeet-ctc-110m-en-int8/` (gitignored, ~126MB on disk). Ran `spikes/voice_asr.py` against the model's own bundled `test_wavs/0.wav` (7.43s, a sentence from a public-domain audiobook) and `test_wavs/1.wav` (0.99s, "I love you") — no synthetic data, real speech. Measured wall-clock decode time with `time.perf_counter()` around `recognizer.decode_stream()`, excluding one-time model load.

**Result.**
- Model load (one-time, at process start): ~1960ms.
- `test_wavs/0.wav` (7.43s audio): decode latency 295–321ms across two runs; transcript exactly correct (verified by ear against the known text of the clip).
- `test_wavs/1.wav` (0.99s audio): decode latency 48ms; transcript exactly correct ("I love you").
- Decode latency scales with audio length and is well under 1s even for a long utterance; a typical 2-4s voice command would be in the ~80-170ms range by extrapolation.
- **Live mic test (your voice, 5s recording):** decode latency **190.2ms** — consistent with the wav-file numbers above, confirming decode speed holds on real mic input too. Transcript: `'Hello, this is Api and this is SM'` — garbled relative to what was almost certainly said (reads like a mangled "this is Abhijay and this is Halo"). The clean bundled test clips transcribed perfectly; live mic audio (room noise, mic quality, no VAD trimming silence) did not.

**Decision (round 1).** **Latency: resolved, well under the 1s threshold** — Parakeet CTC 110M int8 is fast enough as-is, on both clean and live audio; no need to drop to a smaller model for speed. **Accuracy: not resolved by this spike** — the live transcript was noticeably wrong, matching the Day 0 risk register's "voice recognition weak on your accent" risk.

**Round 2 — transducer + VAD follow-up.** Tried the two levers identified in round 1:
- **Transducer variant (`sherpa-onnx-nemo-parakeet_tdt_transducer_110m-en-36000-int8`): dead end.** Fails to load at all — `OfflineRecognizer.from_transducer` raises `'vocab_size' does not exist in the metadata` before touching any audio, on both VAD and no-VAD paths, on the exact same tokens/encoder/decoder/joiner files sherpa-onnx itself exported. This is a model-loading incompatibility between this sherpa-onnx version's generic transducer loader and NeMo Parakeet TDT's transducer export (its extra duration-prediction head likely doesn't match the metadata schema the C++ loader expects for a standard RNN-T). Not pursued further; `spikes/voice_asr.py --model transducer` is left in place but documented as broken.
- **VAD silence trimming: implemented, and had a real bug that's now fixed.** First attempt fed the whole recording to `accept_waveform()` in one call, which silently mis-processed it (chopped 7.43s of real speech down to 0.32s, empty transcript). Fix: Silero VAD v5 must be fed in fixed 512-sample windows, not one large buffer — confirmed by manual chunking, then fixed in `trim_silence()`. Re-verified correct on both bundled clean clips (0.wav: transcript fully correct, trimmed 118960→102656 samples; 1.wav: "I love you." exact, trimmed 15882→15392).
- **VAD on live mic audio: mechanically correct, but did not fix accuracy.** Two takes of "Hello, this is a sample recording" (saved to `spikes/my_voice.wav`, overwritten both times — only the printed output survives) gave **two different wrong transcripts**: `'Hello, this is Asseambled recording'` (85.6ms, trimmed 80000→31264 samples) and `'He know this is a samplple recording'` (84.2ms, trimmed 80000→27360 samples). Both clipped "Hello" at the start. This binding's `SileroVadModelConfig` exposes no onset/offset padding option, so VAD is almost certainly shaving the attack off the first word on every take — and the inconsistency between two takes of the same phrase suggests the int8-quantized model itself is also a real accuracy ceiling here, not just a VAD artifact.

**Decision (final for this spike).** Stop here rather than keep iterating blind on a "quick follow-up" that's now run two rounds. **Latency is a solved problem** (max 86ms seen on live audio, >900ms of budget unused) — there's real headroom to spend on a bigger, non-quantized model later if voice becomes a priority. **Accuracy is not solved**, and the fix isn't VAD tuning — it's most likely the **int8 quantization** trading accuracy for speed we don't need. For v0.1, per the Day 0 risk register's own fallback: **typing and push-to-talk remain the primary input path**; voice is a nice-to-have, not launch-blocking. If Day 5 has spare time, the next real lever to try is the **full-precision (non-int8) Parakeet CTC model** or a different model family (e.g. `faster-whisper` small), not more VAD work — we have the latency budget to afford a much heavier model and still land well under 1s.

---

## 2026-10-10 — pywebview frameless/always-on-top window (Windows)

**Question.** Can pywebview create a frameless, always-on-top window at 260x44 top-centre on Windows, and can a JS call resize it to 420x600 live, without flicker or losing always-on-top?

**Method.** Wrote `spikes/pywebview_window.py`: a frameless, on-top, 260x44 window centred at the top of the primary screen, with a JS-triggered `pywebview.api.resize()` call that grows it to 420x600. Ran a headless import/backend-resolution sanity check myself (no window opened) to confirm the library and its Windows backend load; the window's visual appearance and behavior need your eyes.

**Result.**
- pywebview 6.2.1 imports cleanly; `webview.screens` resolves without error: `[1536x960 at 0,0 1.25x]` (one monitor detected, backend — WebView2 on Windows — initializes).
- Visual confirmation (your run): window appeared frameless at the top of the screen, was draggable (`easy_drag=True` works), and clicking "Resize to HUD" grew it to 420x600 successfully.
- Not explicitly re-confirmed: always-on-top behaviour when another window is focused, and whether the resize was flicker-free or showed square corners instead of the HTML's rounded ones. Not treated as open questions worth a second round for a 45-minute spike — low-severity cosmetic items to watch for during Day 2's real HUD build, not blockers.

**Decision.** pywebview works as the HUD host: frameless, positioned, draggable, and JS-driven resize all function on this machine. Proceed with pywebview per the architecture; no fallback (square window, Electron) needed.

---

## 2026-10-10 — claude-agent-sdk against a scratch repo

**Question.** Does `claude-agent-sdk` run against a local repo, stream every message type, and correctly invoke the `can_use_tool` permission callback for a tool call that isn't pre-approved?

**Method.** Created `tests/fixtures/demo_repo`: a tiny FastAPI app (`GET /ping`) with one passing pytest test, its own git repo (separate `.git`, one commit). Ran `spikes/claude_worker_probe.py` against it, with `cwd` set to the fixture repo, logging every SDK message type and whether `can_use_tool` fired.

**Result.**
- All 5 message types that occurred streamed correctly: `SystemMessage`, `RateLimitEvent`, `AssistantMessage`, `UserMessage`, `ResultMessage` (`StreamEvent`/`ConversationResetMessage` didn't occur in this run — partial-message streaming wasn't requested and no session reset happened; not a gap).
- `can_use_tool` **fired** in both runs — confirmed working. It fired for `PowerShell`/`Bash` calls that execute an actual command (e.g. `uv run pytest -q`), but notably **did not fire** for some read-only calls (`Glob`, a plain `git ls-files` listing) — Claude Code's own built-in auto-mode risk classifier pre-approves some read-only operations before ever consulting the SDK's callback, rather than every tool call being routed through it uniformly. This is a real nuance to design around, not a spike failure.
- `claude-agent-sdk` (0.2.165) needed no separate API key or auth setup — it shells out to the already-authenticated `claude` CLI binary on PATH, so it reused this machine's existing Claude Code login.
- Denying every tool call and hitting `max_turns=3` makes the underlying CLI subprocess exit non-zero even after it streamed a final `ResultMessage(subtype='error_max_turns', ...)`; `claude_agent_sdk.query()` re-raises this as `ResultError` from the async generator. A caller (the future `claude_worker.py`) must wrap the `async for` loop in try/except for this — it can't assume a clean return just because a `ResultMessage` was seen.
- Real cost: ~$0.08–$0.27 and ~1–2% of the 5-hour rate-limit window per 3-4 turn spike run, charged against this Claude Code session's own usage, not a separate key.

**Decision.** claude-agent-sdk works for the Day 4 coding worker: streaming, message mapping to `HaloEvent`s (via `parent_tool_use_id` for sub-agents, matching `docs/ARCHITECTURE.md`), and the permission hook all function and need no separate credential plumbing. Two concrete design notes to carry into Day 4, not fallback triggers: (1) don't rely on `can_use_tool` alone to gate every tool — the built-in classifier pre-approves some reads, so `claude_worker.py`'s own `allowed_tools`/policy config should be explicit about what's pre-approved rather than assuming the callback sees everything; (2) always wrap the message loop in try/except for `ResultError`, since an error-terminated run (timeout, max_turns, denied-into-a-corner) still needs its partial events/cost captured, not just swallowed as an unhandled exception.

---

## 2026-10-12 — Tool calling and JSON-schema validity (profile `nvidia-api`)

**Question.** Does each Nemotron tier produce valid tool calls and valid JSON-schema output at >= 90%, and at what latency and cost?

**Method.** `spikes/tool_calling_probe.py`: per tier, 10 tool-call prompts (3 tools) and 10 router prompts against the `Intent` schema, structured_mode `json_schema`, first attempt only (no retry), one call at a time. 60 calls total, hard-capped.

| tier | model id | tool call valid | tool call correct | JSON valid | JSON correct | median latency | tokens in/out | cost |
|---|---|---|---|---|---|---|---|---|
| nano | `nvidia/nemotron-3.5-lightning-30b-a3b` | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 2371 ms | 7941/6956 | price unknown |
| super | `nvidia/nemotron-3-super-120b-a12b` | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 975 ms | 7941/2207 | price unknown |
| ultra | `nvidia/nemotron-3-ultra-550b-a55b` | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 2887 ms | 7941/1975 | price unknown |

**Decisions.**
- Nano tool calls >= 90%: **yes**, Nano does tool calls.
- JSON-schema output reliable on Nano: **yes** in `json_schema` mode.

---

## 2026-10-27 — Tool calling and JSON-schema validity (profile `token-factory`)

**Question.** Does each Nemotron tier produce valid tool calls and valid JSON-schema output at >= 90%, and at what latency and cost?

**Method.** `spikes/tool_calling_probe.py`: per tier, 10 tool-call prompts (3 tools) and 10 router prompts against the `Intent` schema, structured_mode `json_schema`, first attempt only (no retry), one call at a time. 60 calls total, hard-capped.

| tier | model id | tool call valid | tool call correct | JSON valid | JSON correct | median latency | tokens in/out | cost |
|---|---|---|---|---|---|---|---|---|
| nano | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 1219 ms | 7941/3319 | price unknown |
| super | `nvidia/nemotron-3-super-120b-a12b` | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 1243 ms | 8771/1755 | price unknown |
| ultra | `nvidia/Nemotron-3-Ultra-550b-a55b` | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 10/10 (100%) | 971 ms | 8291/2200 | price unknown |

**Decisions.**
- Nano tool calls >= 90%: **yes**, Nano does tool calls.
- JSON-schema output reliable on Nano: **yes** in `json_schema` mode.

## 2026-10-27 — router score and thinking mode on Nebius Token Factory

**Question.** On the submission profile (Nemotron on Nebius Token Factory), how accurate and fast is the Nano router on the 20-case golden set, and does turning thinking off (`chat_template_kwargs.enable_thinking=false`) help?

**Method.** Live, profile `token-factory`, Nano first and Super on low confidence (the shipped cascade), 20 utterances from `evals/router_golden.yaml`, one call at a time. Plus 3 probe calls per setting for latency.

| setting | router score | mean / max per request |
|---|---|---|
| shipped config (thinking default) | **20/20** | 1.7 s / 10.5 s |
| thinking off | 18/20 | 0.8 s / 2.3 s |

With thinking off the two misses were the ambiguous cases (a general programming question routed to `code.task`, and "what should I work on today?" routed to `code.task` instead of `work.start`).

**Decision.** Keep thinking on for Token Factory (no `extra_body`). Thinking off is about twice as fast but dropped two ambiguous cases; the shipped number is 20/20. The dev profile still sends thinking off (it scored 20/20 there and was much slower with it on). The tool-calling spike above (60/60 on all three tiers) ran on this profile too. Costs are unknown until prices are added to the config.
