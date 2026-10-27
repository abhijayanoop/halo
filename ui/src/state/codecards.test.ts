import { describe, expect, it } from "vitest";
import type { HaloEvent } from "../types/generated/HaloEvent";
import { initialState, reduce } from "./reducer";
import { selectView } from "../view";

let n = 0;
const ev = (
  type: HaloEvent["type"],
  payload: Record<string, unknown> = {},
): HaloEvent => {
  n += 1;
  return {
    id: `K${String(n).padStart(4, "0")}`,
    run_id: "R1",
    ts: new Date(Date.UTC(2026, 9, 27, 10, 0, 0, n * 100)).toISOString(),
    type,
    title: `${type} title`,
    payload,
  };
};

const briefPayload = {
  approval_id: "B1",
  action: "Start coding task",
  detail: "Add rate limiting",
  risk: "medium",
  step_index: 0,
  kind: "code.brief",
  project: "halo",
  mode: "implement",
  brief: {
    goal: "Add rate limiting",
    acceptance_criteria: ["Over-limit requests get 429"],
    likely_files: ["src/webhook.py"],
    test_cmd: "uv run pytest -q",
    constraints: ["No new dependencies"],
    out_of_scope: ["Auth"],
  },
};

const resultPayload = {
  approval_id: "X1",
  action: "Review the result",
  detail: "Added the limiter",
  risk: "high",
  step_index: 0,
  kind: "code.result",
  project: "halo",
  iteration: 2,
  can_iterate: true,
  notice: "Could not merge: main checkout has uncommitted changes",
  cost_inr: "11.40",
  branch: "halo/add-rate-limiting-ab12cd",
  worktree: "C:/x/.halo-worktrees/halo/add-rate-limiting-ab12cd",
  status: "done",
  summary: "Added the limiter",
  tests: { passed: false, exit_code: 1, timed_out: false, tail: "1 failed" },
  review: { result: "concerns", summary: "Missing a test", issues: ["no 429 test"] },
  diff_stat: "1 file changed, 9 insertions(+)",
  changed_files: ["src/webhook.py"],
};

describe("code cards in the reducer", () => {
  it("reads the brief card out of the payload", () => {
    const s = reduce(initialState, ev("approval.requested", briefPayload));
    const a = s.pendingApprovals[0];
    expect(a.kind).toBe("code.brief");
    expect(a.project).toBe("halo");
    expect(a.brief).toEqual({
      goal: "Add rate limiting",
      acceptanceCriteria: ["Over-limit requests get 429"],
      likelyFiles: ["src/webhook.py"],
      testCmd: "uv run pytest -q",
      constraints: ["No new dependencies"],
      outOfScope: ["Auth"],
    });
  });

  it("reads the result card out of the payload", () => {
    const s = reduce(initialState, ev("approval.requested", resultPayload));
    const r = s.pendingApprovals[0].result;
    expect(s.pendingApprovals[0].kind).toBe("code.result");
    expect(r).toMatchObject({
      status: "done",
      summary: "Added the limiter",
      iteration: 2,
      canIterate: true,
      costInr: "11.40",
      branch: "halo/add-rate-limiting-ab12cd",
      diffStat: "1 file changed, 9 insertions(+)",
      changedFiles: ["src/webhook.py"],
      notice: "Could not merge: main checkout has uncommitted changes",
      tests: { passed: false, exitCode: 1, timedOut: false, tail: "1 failed" },
      review: { result: "concerns", summary: "Missing a test", issues: ["no 429 test"] },
    });
  });

  it("a plain permission request has no code card", () => {
    const s = reduce(
      initialState,
      ev("approval.requested", { approval_id: "P1", action: "app.open", risk: "low" }),
    );
    expect(s.pendingApprovals[0].kind).toBeUndefined();
    expect(s.pendingApprovals[0].brief).toBeUndefined();
    expect(s.pendingApprovals[0].result).toBeUndefined();
  });

  it("a malformed code card falls back to a plain card instead of crashing", () => {
    const s = reduce(
      initialState,
      ev("approval.requested", { ...briefPayload, brief: "nonsense" }),
    );
    expect(s.pendingApprovals[0].kind).toBeUndefined();
    const r = reduce(
      initialState,
      ev("approval.requested", { ...resultPayload, tests: null }),
    );
    expect(r.pendingApprovals[0].kind).toBeUndefined();
  });

  it("resolving the card clears it", () => {
    let s = reduce(initialState, ev("approval.requested", briefPayload));
    s = reduce(s, ev("approval.resolved", { approval_id: "B1", grant: "allow_once" }));
    expect(s.pendingApprovals).toEqual([]);
  });
});

describe("the view for code cards", () => {
  it("shows the brief and result views, which win over the bar and the panel", () => {
    const brief = reduce(initialState, ev("approval.requested", briefPayload));
    expect(selectView(brief, false)).toBe("brief");
    expect(selectView(brief, true)).toBe("brief");
    const result = reduce(initialState, ev("approval.requested", resultPayload));
    expect(selectView(result, false)).toBe("result");
  });

  it("an ordinary permission card is still the small card", () => {
    const s = reduce(
      initialState,
      ev("approval.requested", { approval_id: "P1", action: "app.open", risk: "low" }),
    );
    expect(selectView(s, false)).toBe("card");
  });
});

describe("the recorded coding run", () => {
  it("replays to a run waiting on its result card, with the brief already answered", async () => {
    const { default: raw } = await import("../mock/code-task-run.jsonl?raw");
    const { parseJsonl, reduceAll } = await import("./reducer");
    const s = reduceAll(parseJsonl(raw));
    expect(s.pendingApprovals).toHaveLength(1);
    expect(s.pendingApprovals[0].kind).toBe("code.result");
    expect(s.pendingApprovals[0].result?.tests.passed).toBe(true);
    expect(selectView(s, false)).toBe("result");
    expect(s.runs.RUNC.agents.sub1?.status).toBe("done");
  });
});
