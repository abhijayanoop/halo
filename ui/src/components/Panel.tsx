import { motion } from "framer-motion";
import { type CSSProperties, type FormEvent, useRef, useState } from "react";
import type { Api } from "../api";
import { HaloMascot } from "../character/HaloMascot";
import { moodSpec } from "../character/spec";
import type {
  AgentNode,
  HaloState,
  RunView,
  TimelineItem,
} from "../state/reducer";
import { runningAgents, useGaze } from "./CollapsedBar";
import { MemoryTab } from "./MemoryTab";

const TABS = ["Now", "Approvals", "Memory", "Ledger", "History"] as const;
type Tab = (typeof TABS)[number];

const duration = (ms: number) =>
  ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;

type StepState = "running" | "done" | "failed" | "info";

/** Where a timeline row is: a step with no end yet is running, a step that
 *  ended badly failed, anything that is not a step is just information. */
function stepState(item: TimelineItem): StepState {
  if (item.type !== "step.started") return "info";
  if (item.durationMs === undefined) return "running";
  return ["error", "failed", "denied"].includes(item.stepStatus ?? "")
    ? "failed"
    : "done";
}

const DOT: Record<StepState, { glyph: string; style: string }> = {
  running: { glyph: "●", style: "animate-pulse text-violet-300" },
  done: { glyph: "✓", style: "text-emerald-300" },
  failed: { glyph: "✕", style: "text-red-300" },
  info: { glyph: "•", style: "text-ink-faint" },
};

/** Roots first, each followed by its children, with how deep each one sits. */
function agentRows(
  run: RunView | undefined,
): { node: AgentNode; depth: number }[] {
  if (!run) return [];
  const nodes = Object.values(run.agents);
  const rows: { node: AgentNode; depth: number }[] = [];
  const walk = (parentId: string | null, depth: number) => {
    for (const node of nodes.filter((n) => n.parentId === parentId)) {
      rows.push({ node, depth });
      walk(node.id, depth + 1);
    }
  };
  walk(null, 0);
  return rows;
}

const HEADING =
  "pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-faint";

function NowTab({ run }: { run: RunView | undefined }) {
  if (!run)
    return (
      <div className="flex h-full flex-col items-center justify-center gap-1 p-6 text-center">
        <p className="text-sm text-ink">Nothing running.</p>
        <p className="text-xs text-ink-dim">Ask me something below.</p>
      </div>
    );
  const agents = agentRows(run);
  return (
    <div className="flex flex-col gap-4 p-4">
      {agents.length > 0 && (
        <section>
          <h3 className={HEADING}>Helpers</h3>
          <ul aria-label="Helpers" className="flex flex-col gap-0.5">
            {agents.map(({ node, depth }) => (
              <li
                key={node.id}
                data-testid="agent-node"
                data-depth={depth}
                style={{ paddingLeft: depth * 16 }}
                className="flex items-center gap-2 text-[13px] text-ink"
              >
                {depth > 0 && (
                  <span aria-hidden className="text-ink-faint">
                    └
                  </span>
                )}
                <span
                  className={
                    node.status === "running"
                      ? "animate-pulse text-violet-300"
                      : "text-ink-faint"
                  }
                >
                  ●
                </span>
                {node.title}
              </li>
            ))}
          </ul>
        </section>
      )}
      <section>
        <h3 className={HEADING}>Steps</h3>
        <ol aria-label="Timeline" className="flex flex-col gap-1">
          {run.timeline.map((item) => {
            const state = stepState(item);
            return (
              <motion.li
                key={item.id}
                data-testid="timeline-item"
                data-status={state}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.18 }}
                className="tile rounded-lg px-2.5 py-1.5 text-[13px] text-ink"
              >
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className={`w-3 text-center text-xs ${DOT[state].style}`}
                  >
                    {DOT[state].glyph}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{item.title}</span>
                  {item.durationMs !== undefined && (
                    <span className="shrink-0 font-mono text-[10px] tabular-nums text-ink-dim">
                      {duration(item.durationMs)}
                    </span>
                  )}
                </div>
                {item.memories && (
                  // The exact memories that went into the prompt, and where each came from.
                  <ul
                    aria-label="Memories used"
                    className="mt-1 flex flex-col gap-1 pl-5"
                  >
                    {item.memories.map((m) => (
                      <li key={`${m.note}-${m.fact}`} className="leading-snug">
                        <span className="text-ink">{m.fact}</span>
                        <span className="block font-mono text-[10px] text-ink-faint">
                          {m.note} · {m.source} · {m.trust}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </motion.li>
            );
          })}
        </ol>
      </section>
    </div>
  );
}

export function Panel({
  halo,
  api,
  onCollapse,
}: {
  halo: HaloState;
  api: Api;
  onCollapse: () => void;
}) {
  const [tab, setTab] = useState<Tab>("Now");
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const run = halo.activeRunId ? halo.runs[halo.activeRunId] : undefined;
  const progress = run?.progress;
  const spec = moodSpec(halo.mood);
  const helpers = runningAgents(halo);
  const mascotBox = useRef<HTMLDivElement>(null);
  const gaze = useGaze(mascotBox);

  const live = run?.status === "running" || run?.status === "paused";

  const stop = async () => {
    if (!run) return;
    setError(null);
    try {
      await api.stop?.(run.id);
    } catch {
      setError("Couldn't stop that run. It may already be done.");
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const request = text.trim();
    if (!request) return;
    setError(null);
    try {
      await api.run(request);
      setText("");
    } catch {
      setError("Couldn't reach Halo. Is it still running?");
    }
  };

  return (
    <section
      style={{ "--ring": spec.ring } as CSSProperties}
      className="plate flex h-[360px] w-[640px] overflow-hidden rounded-2xl text-ink"
    >
      {/* The rail: who Halo is right now. */}
      <aside className="flex w-[188px] shrink-0 flex-col gap-3 border-r border-line p-4">
        <div ref={mascotBox} className="-ml-1 mt-1">
          <HaloMascot
            mood={halo.mood}
            agents={helpers}
            progress={progress ? progress.step / progress.of : null}
            gaze={gaze}
            size={96}
          />
        </div>
        <div className="min-w-0">
          <div
            className="text-[10px] font-semibold uppercase tracking-wider"
            style={{ color: spec.ring }}
          >
            {spec.label}
          </div>
          <motion.div
            key={halo.statusLine}
            initial={{ opacity: 0, y: 3 }}
            animate={{ opacity: 1, y: 0 }}
            className="line-clamp-3 pt-0.5 text-[13px] font-medium leading-snug"
          >
            {halo.statusLine}
          </motion.div>
        </div>

        {run?.request && (
          <div className="min-w-0">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
              You asked
            </div>
            <p
              data-testid="run-request"
              className="line-clamp-3 pt-0.5 text-[12px] leading-snug text-ink-dim"
            >
              {run.request}
            </p>
          </div>
        )}

        <div className="flex flex-col gap-1.5 text-[11px] text-ink-dim">
          {progress && (
            <div>
              <div className="flex justify-between">
                <span>Step</span>
                <span className="font-mono tabular-nums text-ink">
                  {progress.step}/{progress.of}
                </span>
              </div>
              <div className="mt-1 h-[2px] overflow-hidden rounded-full bg-line">
                <motion.div
                  className="h-full rounded-full"
                  style={{ background: spec.ring }}
                  animate={{ width: `${(progress.step / progress.of) * 100}%` }}
                  transition={{ type: "spring", stiffness: 200, damping: 26 }}
                />
              </div>
            </div>
          )}
          {run && (
            <div className="flex justify-between">
              <span>Cost</span>
              <span
                data-testid="run-cost"
                className="font-mono tabular-nums text-ink"
              >
                ₹{run.costInr.toFixed(2)}
              </span>
            </div>
          )}
          {helpers > 0 && (
            <div className="flex justify-between">
              <span>Helpers</span>
              <span className="font-mono tabular-nums text-ink">
                <span data-testid="helper-count">{helpers}</span>{" "}
                <span className="font-sans text-ink-dim">
                  {helpers === 1 ? "helper" : "helpers"}
                </span>
              </span>
            </div>
          )}
        </div>

        {live && (
          <button
            type="button"
            onClick={() => void stop()}
            className="mt-auto rounded-md border border-line px-2.5 py-1.5 text-xs font-medium text-ink transition hover:border-red-400/60 hover:text-red-200 active:scale-95"
          >
            ■ Stop
          </button>
        )}
      </aside>

      {/* The content: tabs, the tab, and where you ask. */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center border-b border-line pl-2 pr-1">
          <div role="tablist" className="flex flex-1 gap-1">
            {TABS.map((name) => (
              <button
                key={name}
                type="button"
                role="tab"
                aria-selected={tab === name}
                onClick={() => setTab(name)}
                className={`-mb-px border-b-2 px-2.5 py-2.5 text-xs font-medium transition ${
                  tab === name
                    ? "border-ink text-ink"
                    : "border-transparent text-ink-dim hover:text-ink"
                }`}
              >
                {name}
                {name === "Memory" && halo.proposedMemories.length > 0 && (
                  <span className="ml-1.5 rounded-full bg-ink px-1.5 text-[10px] font-semibold text-bg">
                    {halo.proposedMemories.length}
                  </span>
                )}
              </button>
            ))}
          </div>
          <button
            type="button"
            aria-label="Collapse"
            onClick={onCollapse}
            className="rounded-md px-2 py-1 text-ink-dim transition hover:bg-raised-2 hover:text-ink"
          >
            ✕
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto">
          {tab === "Now" ? (
            <NowTab run={run} />
          ) : tab === "Memory" ? (
            <MemoryTab proposals={halo.proposedMemories} api={api} />
          ) : (
            <p data-testid="tab-stub" className="p-4 text-sm text-ink-dim">
              {tab} is coming soon.
            </p>
          )}
        </div>

        <form onSubmit={submit} className="border-t border-line p-3">
          {error && (
            <p role="alert" className="pb-1.5 text-xs text-red-300">
              {error}
            </p>
          )}
          <div className="tile flex items-center gap-2 rounded-lg pr-1.5 focus-within:border-ink-dim">
            <input
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Ask Halo to do something…"
              aria-label="Ask Halo"
              className="min-w-0 flex-1 bg-transparent px-3 py-2 text-sm outline-none placeholder:text-ink-faint"
            />
            <button
              type="submit"
              aria-label="Send"
              disabled={!text.trim()}
              className="rounded-md bg-ink px-2.5 py-1 text-sm font-semibold text-bg transition enabled:hover:bg-white disabled:opacity-25"
            >
              ↑
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
