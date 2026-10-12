import { type FormEvent, useState } from "react";
import type { Api } from "../api";
import { HaloMascot } from "../character/HaloMascot";
import { moodSpec } from "../character/spec";
import type { AgentNode, HaloState, RunView } from "../state/reducer";
import { runningAgents } from "./CollapsedBar";

const TABS = ["Now", "Approvals", "Memory", "Ledger", "History"] as const;
type Tab = (typeof TABS)[number];

const duration = (ms: number) =>
  ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`;

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

function NowTab({ run }: { run: RunView | undefined }) {
  if (!run)
    return (
      <p className="p-4 text-sm text-slate-400">
        Nothing running. Ask me something below.
      </p>
    );
  const agents = agentRows(run);
  return (
    <div className="flex flex-col gap-3 overflow-y-auto p-3">
      {agents.length > 0 && (
        <ul aria-label="Helpers" className="flex flex-col gap-1">
          {agents.map(({ node, depth }) => (
            <li
              key={node.id}
              data-testid="agent-node"
              data-depth={depth}
              style={{ paddingLeft: depth * 16 }}
              className="text-[13px] text-slate-200"
            >
              <span
                className={
                  node.status === "running"
                    ? "text-violet-300"
                    : "text-slate-500"
                }
              >
                ●
              </span>{" "}
              {node.title}
            </li>
          ))}
        </ul>
      )}
      <ol aria-label="Timeline" className="flex flex-col gap-1">
        {run.timeline.map((item) => (
          <li
            key={item.id}
            data-testid="timeline-item"
            className="flex justify-between gap-2 text-[13px] text-slate-200"
          >
            <span className="truncate">{item.title}</span>
            {item.durationMs !== undefined && (
              <span className="shrink-0 tabular-nums text-slate-500">
                {duration(item.durationMs)}
              </span>
            )}
          </li>
        ))}
      </ol>
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
    <section className="flex h-[600px] w-[420px] flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-900/85 text-slate-100 shadow-xl backdrop-blur">
      <header className="flex items-center gap-3 border-b border-white/10 p-3">
        <HaloMascot
          mood={halo.mood}
          agents={runningAgents(halo)}
          progress={progress ? progress.step / progress.of : null}
          size={56}
        />
        <div className="min-w-0 flex-1">
          <div className="text-xs uppercase tracking-wide text-slate-400">
            {moodSpec(halo.mood).label}
          </div>
          <div className="truncate text-sm">{halo.statusLine}</div>
          {run && (
            <div
              data-testid="run-cost"
              className="text-xs tabular-nums text-slate-500"
            >
              ₹{run.costInr.toFixed(2)}
            </div>
          )}
        </div>
        <button
          type="button"
          aria-label="Collapse"
          onClick={onCollapse}
          className="rounded-md px-2 py-1 text-slate-400 hover:bg-white/10"
        >
          ✕
        </button>
      </header>

      <div
        role="tablist"
        className="flex gap-1 border-b border-white/10 px-2 pt-1"
      >
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
            className={`rounded-t-md px-2 py-1 text-xs ${
              tab === name
                ? "bg-white/10 text-white"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            {name}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === "Now" ? (
          <NowTab run={run} />
        ) : (
          <p data-testid="tab-stub" className="p-4 text-sm text-slate-400">
            {tab} is coming soon.
          </p>
        )}
      </div>

      <form onSubmit={submit} className="border-t border-white/10 p-2">
        {error && (
          <p role="alert" className="pb-1 text-xs text-red-300">
            {error}
          </p>
        )}
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask Halo to do something…"
          aria-label="Ask Halo"
          className="w-full rounded-lg bg-white/10 px-3 py-2 text-sm outline-none placeholder:text-slate-500 focus:ring-1 focus:ring-violet-400"
        />
      </form>
    </section>
  );
}
