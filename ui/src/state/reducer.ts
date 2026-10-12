// The UI is a function of the event stream: everything on screen is derived
// from HaloEvents by this reducer and nothing else. That is what makes replaying
// a past run free. Mood is decided in Python and arrives as `mood` events; the
// UI never works it out itself.
import type { HaloEvent } from "../types/generated/HaloEvent";

export const MOODS = [
  "asleep",
  "waking",
  "idle",
  "listening",
  "thinking",
  "focused",
  "delegating",
  "careful",
  "remembering",
  "asking",
  "guarding",
  "delighted",
  "confused",
] as const;
export type Mood = (typeof MOODS)[number];

export type RunStatus = "running" | "paused" | "finished" | "failed";
export type RunResult = "ok" | "error" | "denied";
export type Risk = "low" | "medium" | "high";

export interface TimelineItem {
  id: string;
  type: HaloEvent["type"];
  title: string;
  ts: string;
  agentId: string | null;
  durationMs?: number;
  stepStatus?: string;
}

export interface AgentNode {
  id: string;
  parentId: string | null;
  title: string;
  status: "running" | "done";
}

export interface RunView {
  id: string;
  request: string;
  status: RunStatus;
  result?: RunResult;
  failure?: string;
  startedAt: string;
  finishedAt?: string;
  timeline: TimelineItem[];
  openSteps: string[]; // timeline ids of step.started events not yet finished
  progress: { step: number; of: number } | null;
  agents: Record<string, AgentNode>;
  costInr: number;
}

export interface PendingApproval {
  approvalId: string;
  runId: string;
  action: string;
  detail: string;
  risk: Risk;
  stepIndex: number | null;
  requestedAt: string;
}

export interface HaloState {
  runs: Record<string, RunView>;
  order: string[];
  activeRunId: string | null;
  pendingApprovals: PendingApproval[];
  mood: Mood;
  moodSince: string | null;
  statusLine: string;
  blocked: { runId: string; reason: string } | null;
  totalCostInr: number;
  seen: Record<string, true>;
}

export const initialState: HaloState = {
  runs: {},
  order: [],
  activeRunId: null,
  pendingApprovals: [],
  mood: "idle",
  moodSince: null,
  statusLine: "Ready",
  blocked: null,
  totalCostInr: 0,
  seen: {},
};

const num = (value: unknown): number | null => {
  const n = typeof value === "string" ? Number(value) : value;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
};
const str = (value: unknown): string | null =>
  typeof value === "string" ? value : null;
const isMood = (value: unknown): value is Mood => MOODS.includes(value as Mood);

function emptyRun(id: string, request: string, ts: string): RunView {
  return {
    id,
    request,
    status: "running",
    startedAt: ts,
    timeline: [],
    openSteps: [],
    progress: null,
    agents: {},
    costInr: 0,
  };
}

function withRun(
  state: HaloState,
  event: HaloEvent,
  update: (run: RunView) => RunView,
): HaloState {
  const run =
    state.runs[event.run_id] ?? emptyRun(event.run_id, event.title, event.ts);
  return {
    ...state,
    runs: { ...state.runs, [event.run_id]: update(run) },
    order: state.order.includes(event.run_id)
      ? state.order
      : [...state.order, event.run_id],
  };
}

function toTimelineItem(event: HaloEvent): TimelineItem {
  return {
    id: event.id,
    type: event.type,
    title: event.title,
    ts: event.ts,
    agentId: event.agent_id ?? null,
  };
}

export function reduce(state: HaloState, event: HaloEvent): HaloState {
  if (state.seen[event.id]) return state;
  const base: HaloState = {
    ...state,
    seen: { ...state.seen, [event.id]: true },
  };
  const payload = event.payload ?? {};

  if (event.type === "mood") {
    const mood = payload.mood;
    if (!isMood(mood)) return base;
    // The core writes the status line onto its mood events (a template at once,
    // then a better one from Nano), so the line always agrees with the face.
    const line = str(payload.line);
    return {
      ...base,
      mood,
      moodSince: event.ts,
      statusLine: line ?? base.statusLine,
    };
  }

  if (event.type === "cost.updated") {
    const cost = num(payload.cost_inr) ?? 0;
    const next = withRun(base, event, (run) => ({
      ...run,
      costInr: run.costInr + cost,
    }));
    return { ...next, totalCostInr: base.totalCostInr + cost };
  }

  let next = withRun(base, event, (run) => ({
    ...run,
    timeline: [...run.timeline, toTimelineItem(event)],
  }));
  next = { ...next, statusLine: event.title };

  switch (event.type) {
    case "run.started":
      return {
        ...withRun(next, event, (run) => ({
          ...run,
          request: str(payload.request) ?? event.title,
          status: "running",
          startedAt: event.ts,
        })),
        activeRunId: event.run_id,
        blocked: null,
      };

    case "step.started":
      return withRun(next, event, (run) => {
        const step = num(payload.step);
        const of = num(payload.of);
        return {
          ...run,
          openSteps: [...run.openSteps, event.id],
          progress: step !== null && of !== null ? { step, of } : run.progress,
        };
      });

    case "step.finished":
      return withRun(next, event, (run) => {
        const openId = run.openSteps[run.openSteps.length - 1];
        const opened = run.timeline.find((item) => item.id === openId);
        const step = num(payload.step);
        const of = num(payload.of);
        return {
          ...run,
          openSteps: run.openSteps.slice(0, -1),
          timeline: run.timeline.map((item) =>
            item.id === openId && opened
              ? {
                  ...item,
                  durationMs: Date.parse(event.ts) - Date.parse(opened.ts),
                  stepStatus: str(payload.status) ?? undefined,
                }
              : item,
          ),
          progress: step !== null && of !== null ? { step, of } : run.progress,
        };
      });

    case "approval.requested": {
      const approval: PendingApproval = {
        approvalId: str(payload.approval_id) ?? event.id,
        runId: event.run_id,
        action: str(payload.action) ?? event.title,
        detail: str(payload.detail) ?? "",
        risk: (str(payload.risk) as Risk | null) ?? "medium",
        stepIndex: num(payload.step_index),
        requestedAt: event.ts,
      };
      return {
        ...withRun(next, event, (run) => ({ ...run, status: "paused" })),
        pendingApprovals: [...next.pendingApprovals, approval],
      };
    }

    case "approval.resolved": {
      const id = str(payload.approval_id);
      const index = next.pendingApprovals.findIndex((a) =>
        id ? a.approvalId === id : a.runId === event.run_id,
      );
      const pending =
        index === -1
          ? next.pendingApprovals
          : next.pendingApprovals.filter((_, i) => i !== index);
      const stillWaiting = pending.some((a) => a.runId === event.run_id);
      return {
        ...withRun(next, event, (run) =>
          run.status === "paused" && !stillWaiting
            ? { ...run, status: "running" }
            : run,
        ),
        pendingApprovals: pending,
      };
    }

    case "run.finished":
      return withRun(next, event, (run) => ({
        ...run,
        status: "finished",
        result: (str(payload.status) as RunResult | null) ?? "ok",
        finishedAt: event.ts,
      }));

    case "run.failed":
      return withRun(next, event, (run) => ({
        ...run,
        status: "failed",
        failure: str(payload.reason) ?? event.title,
        finishedAt: event.ts,
      }));

    case "agent.spawned":
      return withRun(next, event, (run) => {
        const id = event.agent_id;
        if (!id) return run;
        const node: AgentNode = {
          id,
          parentId: event.parent_agent_id ?? null,
          title: event.title,
          status: "running",
        };
        return { ...run, agents: { ...run.agents, [id]: node } };
      });

    case "agent.finished":
      return withRun(next, event, (run) => {
        const id = event.agent_id;
        const node = id ? run.agents[id] : undefined;
        return id && node
          ? {
              ...run,
              agents: { ...run.agents, [id]: { ...node, status: "done" } },
            }
          : run;
      });

    case "policy.blocked":
      return { ...next, blocked: { runId: event.run_id, reason: event.title } };

    default:
      return next;
  }
}

export function reduceAll(
  events: HaloEvent[],
  from: HaloState = initialState,
): HaloState {
  return events.reduce(reduce, from);
}

export function parseJsonl(text: string): HaloEvent[] {
  const events: HaloEvent[] = [];
  text.split(/\r?\n/).forEach((line, index) => {
    if (!line.trim()) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(line);
    } catch {
      throw new Error(`line ${index + 1}: not valid JSON`);
    }
    const e = parsed as Partial<HaloEvent> | null;
    if (
      !e ||
      typeof e.id !== "string" ||
      typeof e.run_id !== "string" ||
      typeof e.type !== "string"
    ) {
      throw new Error(`line ${index + 1}: not a HaloEvent`);
    }
    events.push(e as HaloEvent);
  });
  return events;
}
