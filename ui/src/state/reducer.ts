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

export interface RecalledMemory {
  fact: string;
  note: string;
  source: string;
  trust: string;
}

/** A fact Halo thinks is worth keeping, waiting for the user's yes or no. */
export interface ProposedMemory {
  candidateId: string;
  fact: string;
  subject: string;
  source: string;
  trust: string;
}

export interface TimelineItem {
  id: string;
  type: HaloEvent["type"];
  title: string;
  ts: string;
  agentId: string | null;
  durationMs?: number;
  stepStatus?: string;
  /** The memories that went into a prompt, when this step recalled some. */
  memories?: RecalledMemory[];
}

export interface AgentNode {
  id: string;
  parentId: string | null;
  title: string;
  status: "running" | "done";
}

/** Something Halo suggests picking up, with the request that starts it. */
export interface WorkProposal {
  title: string;
  project: string | null;
  request: string;
}

export interface RunView {
  id: string;
  request: string;
  status: RunStatus;
  result?: RunResult;
  failure?: string;
  /** What Halo said back: a chat reply or a recall answer, once the run is done. */
  answer?: string;
  /** What `work.start` suggests: click one to start it. At most three. */
  proposals?: WorkProposal[];
  startedAt: string;
  finishedAt?: string;
  timeline: TimelineItem[];
  openSteps: string[]; // timeline ids of step.started events not yet finished
  progress: { step: number; of: number } | null;
  agents: Record<string, AgentNode>;
  costInr: number;
}

/** The brief of a coding task, as shown on the brief card. */
export interface BriefData {
  goal: string;
  acceptanceCriteria: string[];
  likelyFiles: string[];
  testCmd: string;
  constraints: string[];
  outOfScope: string[];
}

/** What Halo itself found out about a finished coding change. */
export interface ResultData {
  project: string;
  status: string;
  summary: string;
  tests: {
    passed: boolean;
    exitCode: number | null;
    timedOut: boolean;
    tail: string;
  };
  review: {
    result: "pass" | "concerns";
    summary: string;
    issues: string[];
  } | null;
  diffStat: string;
  changedFiles: string[];
  costInr: string;
  branch: string;
  worktree: string;
  iteration: number;
  canIterate: boolean;
  notice: string;
}

export type CodeKind = "code.brief" | "code.result";

export interface PendingApproval {
  approvalId: string;
  runId: string;
  action: string;
  detail: string;
  risk: Risk;
  stepIndex: number | null;
  requestedAt: string;
  /** Set only for the cards of a coding session, and only if their payload is well formed. */
  kind?: CodeKind;
  project?: string;
  brief?: BriefData;
  result?: ResultData;
}

export interface HaloState {
  runs: Record<string, RunView>;
  order: string[];
  activeRunId: string | null;
  pendingApprovals: PendingApproval[];
  proposedMemories: ProposedMemory[];
  mood: Mood;
  moodSince: string | null;
  statusLine: string;
  blocked: { runId: string; reason: string } | null;
  totalCostInr: number;
  /** True once the core has sent a status line on a mood event; from then on
   *  only mood events set the status line (raw event titles are for the timeline). */
  lineFromCore: boolean;
  seen: Record<string, true>;
}

export const initialState: HaloState = {
  runs: {},
  order: [],
  activeRunId: null,
  pendingApprovals: [],
  proposedMemories: [],
  mood: "idle",
  moodSince: null,
  statusLine: "Ready",
  blocked: null,
  totalCostInr: 0,
  lineFromCore: false,
  seen: {},
};

const num = (value: unknown): number | null => {
  const n = typeof value === "string" ? Number(value) : value;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
};
const str = (value: unknown): string | null =>
  typeof value === "string" ? value : null;
const isMood = (value: unknown): value is Mood => MOODS.includes(value as Mood);

const isObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const strings = (value: unknown): string[] | null =>
  Array.isArray(value) && value.every((v) => typeof v === "string")
    ? (value as string[])
    : null;

function parseBrief(value: unknown): BriefData | null {
  if (!isObject(value)) return null;
  const goal = str(value.goal);
  const criteria = strings(value.acceptance_criteria);
  const testCmd = str(value.test_cmd);
  if (goal === null || criteria === null || testCmd === null) return null;
  return {
    goal,
    acceptanceCriteria: criteria,
    likelyFiles: strings(value.likely_files) ?? [],
    testCmd,
    constraints: strings(value.constraints) ?? [],
    outOfScope: strings(value.out_of_scope) ?? [],
  };
}

function parseResult(payload: Record<string, unknown>): ResultData | null {
  const tests = payload.tests;
  if (!isObject(tests) || typeof tests.passed !== "boolean") return null;
  let review: ResultData["review"] = null;
  if (isObject(payload.review)) {
    const r = payload.review;
    const verdict = r.result === "pass" ? "pass" : "concerns";
    review = {
      result: verdict,
      summary: str(r.summary) ?? "",
      issues: strings(r.issues) ?? [],
    };
  }
  return {
    project: str(payload.project) ?? "",
    status: str(payload.status) ?? "",
    summary: str(payload.summary) ?? "",
    tests: {
      passed: tests.passed,
      exitCode: num(tests.exit_code),
      timedOut: tests.timed_out === true,
      tail: str(tests.tail) ?? "",
    },
    review,
    diffStat: str(payload.diff_stat) ?? "",
    changedFiles: strings(payload.changed_files) ?? [],
    costInr: str(payload.cost_inr) ?? "",
    branch: str(payload.branch) ?? "",
    worktree: str(payload.worktree) ?? "",
    iteration: num(payload.iteration) ?? 1,
    canIterate: payload.can_iterate === true,
    notice: str(payload.notice) ?? "",
  };
}

function parseCodeCard(
  payload: Record<string, unknown>,
): Pick<PendingApproval, "kind" | "project" | "brief" | "result"> {
  if (payload.kind === "code.brief") {
    const brief = parseBrief(payload.brief);
    if (brief)
      return { kind: "code.brief", project: str(payload.project) ?? "", brief };
  } else if (payload.kind === "code.result") {
    const result = parseResult(payload);
    if (result)
      return {
        kind: "code.result",
        project: str(payload.project) ?? "",
        result,
      };
  }
  return {};
}

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

function recalled(value: unknown): RecalledMemory[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const found: RecalledMemory[] = [];
  for (const m of value) {
    const fact = str((m as Record<string, unknown>)?.fact);
    if (!fact) continue;
    found.push({
      fact,
      note: str((m as Record<string, unknown>).note) ?? "",
      source: str((m as Record<string, unknown>).source) ?? "",
      trust: str((m as Record<string, unknown>).trust) ?? "",
    });
  }
  return found.length > 0 ? found : undefined;
}

/** The text Halo answered with: the last step result that has a reply or answer. */
function answerFrom(results: unknown): string | undefined {
  if (!Array.isArray(results)) return undefined;
  let found: string | undefined;
  for (const entry of results) {
    const result = (entry as { result?: Record<string, unknown> } | null)?.result;
    const text = str(result?.reply) ?? str(result?.answer);
    if (text && text.trim()) found = text;
  }
  return found;
}

/** The suggestions of a finished `work.start` run; anything malformed is dropped. */
function proposalsFrom(results: unknown): WorkProposal[] | undefined {
  if (!Array.isArray(results)) return undefined;
  let found: WorkProposal[] | undefined;
  for (const entry of results) {
    const list = (entry as { result?: { proposals?: unknown } } | null)?.result
      ?.proposals;
    if (!Array.isArray(list)) continue;
    const items = list.flatMap((p): WorkProposal[] => {
      if (!isObject(p)) return [];
      const title = str(p.title);
      const request = str(p.request);
      if (!title || !request) return [];
      return [{ title, project: str(p.project), request }];
    });
    if (items.length > 0) found = items.slice(0, 3);
  }
  return found;
}

function toTimelineItem(event: HaloEvent): TimelineItem {
  const memories = recalled(event.payload?.memories);
  return {
    id: event.id,
    type: event.type,
    title: event.title,
    ts: event.ts,
    agentId: event.agent_id ?? null,
    ...(memories ? { memories } : {}),
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
      lineFromCore: base.lineFromCore || line !== null,
    };
  }

  // Proposed memories belong to no run: they are not a step and change no mood.
  if (event.type === "memory.proposed") {
    const candidateId = str(payload.candidate_id);
    const fact = str(payload.fact);
    if (!candidateId || !fact) return base;
    if (base.proposedMemories.some((p) => p.candidateId === candidateId))
      return base;
    return {
      ...base,
      proposedMemories: [
        ...base.proposedMemories,
        {
          candidateId,
          fact,
          subject: str(payload.subject) ?? "",
          source: str(payload.source) ?? "agent",
          trust: str(payload.trust) ?? "medium",
        },
      ],
    };
  }
  if (
    (event.type === "memory.saved" || event.type === "memory.forgotten") &&
    str(payload.candidate_id)
  ) {
    const settled = str(payload.candidate_id);
    return {
      ...base,
      proposedMemories: base.proposedMemories.filter(
        (p) => p.candidateId !== settled,
      ),
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
  if (!next.lineFromCore) next = { ...next, statusLine: event.title };

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
        lineFromCore: false,
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
        ...parseCodeCard(payload),
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
        answer: answerFrom(payload.results),
        proposals: proposalsFrom(payload.results),
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
