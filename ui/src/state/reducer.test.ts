import { describe, expect, it } from "vitest";
import notepadRun from "../mock/notepad-run.jsonl?raw";
import type { HaloEvent } from "../types/generated/HaloEvent";
import { initialState, parseJsonl, reduce, reduceAll } from "./reducer";

let counter = 0;
function ev(
  type: HaloEvent["type"],
  payload: Record<string, unknown> = {},
  extra: Partial<HaloEvent> = {},
): HaloEvent {
  counter += 1;
  return {
    id: `E${String(counter).padStart(4, "0")}`,
    run_id: "R1",
    ts: new Date(Date.UTC(2026, 9, 12, 10, 0, 0, counter * 100)).toISOString(),
    type,
    title: `${type} title`,
    payload,
    ...extra,
  };
}

describe("reducer", () => {
  it("starts idle with nothing on screen", () => {
    expect(initialState.mood).toBe("idle");
    expect(initialState.order).toEqual([]);
    expect(initialState.pendingApprovals).toEqual([]);
  });

  it("run.started creates a running run and makes it active", () => {
    const s = reduce(
      initialState,
      ev("run.started", { request: "open Notepad" }),
    );
    expect(s.order).toEqual(["R1"]);
    expect(s.runs.R1).toMatchObject({
      request: "open Notepad",
      status: "running",
    });
    expect(s.activeRunId).toBe("R1");
  });

  it("step events build a timeline with durations and progress", () => {
    const s = reduceAll([
      ev("run.started", { request: "x" }),
      ev("step.started", { step: 2, of: 3, tool: "app.open" }),
      ev("step.finished", { step: 2, of: 3, status: "ok" }),
    ]);
    const steps = s.runs.R1.timeline.filter((t) => t.type === "step.started");
    expect(steps).toHaveLength(1);
    expect(steps[0].durationMs).toBe(100);
    expect(s.runs.R1.progress).toEqual({ step: 2, of: 3 });
  });

  it("approval.requested pauses the run until it is resolved", () => {
    const asked = reduceAll([
      ev("run.started", { request: "x" }),
      ev("approval.requested", {
        approval_id: "A1",
        action: "app.open",
        detail: "{'app': 'Notepad'}",
        risk: "medium",
        step_index: 0,
      }),
    ]);
    expect(asked.pendingApprovals).toEqual([
      expect.objectContaining({
        approvalId: "A1",
        runId: "R1",
        risk: "medium",
        action: "app.open",
      }),
    ]);
    expect(asked.runs.R1.status).toBe("paused");

    const done = reduce(
      asked,
      ev("approval.resolved", { approval_id: "A1", grant: "allow_once" }),
    );
    expect(done.pendingApprovals).toEqual([]);
    expect(done.runs.R1.status).toBe("running");
  });

  it("resolving one approval leaves another pending", () => {
    const s = reduceAll([
      ev("run.started", { request: "x" }),
      ev("approval.requested", {
        approval_id: "A1",
        action: "a",
        detail: "",
        risk: "medium",
      }),
      ev("approval.requested", {
        approval_id: "A2",
        action: "b",
        detail: "",
        risk: "high",
      }),
      ev("approval.resolved", { approval_id: "A1", grant: "deny" }),
    ]);
    expect(s.pendingApprovals.map((a) => a.approvalId)).toEqual(["A2"]);
    expect(s.runs.R1.status).toBe("paused");
  });

  it("mood comes only from mood events, never guessed in the UI", () => {
    const s = reduceAll([
      ev("run.started", { request: "x" }),
      ev("approval.requested", { approval_id: "A" }),
    ]);
    expect(s.mood).toBe("idle");
    expect(
      reduce(s, ev("mood", { mood: "asking", previous: "idle" })).mood,
    ).toBe("asking");
  });

  it("run.finished and run.failed settle the run", () => {
    const ok = reduceAll([
      ev("run.started", { request: "x" }),
      ev("run.finished", { status: "ok" }),
    ]);
    expect(ok.runs.R1).toMatchObject({ status: "finished", result: "ok" });
    const bad = reduceAll([
      ev("run.started", { request: "x" }),
      ev("run.failed", { reason: "boom" }),
    ]);
    expect(bad.runs.R1).toMatchObject({ status: "failed", failure: "boom" });
  });

  it("builds the agent tree from parent_agent_id", () => {
    const s = reduceAll([
      ev("run.started", { request: "x" }),
      ev(
        "agent.spawned",
        {},
        { agent_id: "a1", parent_agent_id: null, title: "Researcher" },
      ),
      ev(
        "agent.spawned",
        {},
        { agent_id: "a2", parent_agent_id: "a1", title: "Reader" },
      ),
      ev("agent.finished", {}, { agent_id: "a2" }),
    ]);
    expect(s.runs.R1.agents.a2).toMatchObject({
      parentId: "a1",
      status: "done",
    });
    expect(s.runs.R1.agents.a1).toMatchObject({
      parentId: null,
      status: "running",
    });
  });

  it("sums cost per run and overall without adding it to the timeline", () => {
    const s = reduceAll([
      ev("run.started", { request: "x" }),
      ev("cost.updated", { cost_inr: "0.40" }),
      ev("cost.updated", { cost_inr: "1.10" }),
    ]);
    expect(s.runs.R1.costInr).toBeCloseTo(1.5);
    expect(s.totalCostInr).toBeCloseTo(1.5);
    expect(s.runs.R1.timeline.map((t) => t.type)).not.toContain("cost.updated");
  });

  it("policy.blocked raises a banner that the next run clears", () => {
    const blocked = reduceAll([
      ev("run.started", { request: "x" }),
      ev(
        "policy.blocked",
        { reason: "hidden instruction" },
        { title: "Blocked a hidden instruction" },
      ),
    ]);
    expect(blocked.blocked).toEqual({
      runId: "R1",
      reason: "Blocked a hidden instruction",
    });
    const next = reduce(
      blocked,
      ev("run.started", { request: "y" }, { run_id: "R2" }),
    );
    expect(next.blocked).toBeNull();
  });

  it("status line follows the latest human-readable event", () => {
    const s = reduceAll([
      ev("run.started", { request: "x" }),
      ev("step.started", {}, { title: "Planning" }),
      ev("cost.updated", {}, { title: "Nano call" }),
      ev("mood", { mood: "thinking" }, { title: "Thinking" }),
    ]);
    expect(s.statusLine).toBe("Planning");
  });

  it("a mood event's line becomes the status line, and a refined line replaces it", () => {
    const s = reduceAll([
      ev("run.started", { request: "x" }),
      ev("mood", { mood: "focused", line: "Opening app" }),
    ]);
    expect(s.statusLine).toBe("Opening app");
    const refined = reduce(
      s,
      ev("mood", { mood: "focused", line: "Opening Notepad", refined: true }),
    );
    expect(refined.statusLine).toBe("Opening Notepad");
    expect(refined.mood).toBe("focused");
  });

  it("a mood event without a line leaves the status line alone", () => {
    const s = reduceAll([
      ev("run.started", { request: "x" }),
      ev("step.started", {}, { title: "Planning" }),
      ev("mood", { mood: "thinking" }),
    ]);
    expect(s.statusLine).toBe("Planning");
  });

  it("once the core has sent a mood line, raw event titles stop overwriting it", () => {
    const s = reduceAll([
      ev("run.started", { request: "x" }),
      ev("mood", { mood: "focused", line: "Opening Notepad" }),
      ev("step.finished", {}, { title: "Finished (error)" }),
      ev("tool.result", {}, { title: "Opened Notepad" }),
    ]);
    expect(s.statusLine).toBe("Opening Notepad");
  });

  it("ignores an event it has already seen (a reconnect can replay)", () => {
    const first = ev("run.started", { request: "x" });
    const once = reduce(initialState, first);
    expect(reduce(once, first)).toBe(once);
  });

  it("replaying the same events always gives the same state", () => {
    const events = parseJsonl(notepadRun);
    expect(reduceAll(events)).toEqual(reduceAll(events));
  });

  it("the recorded Notepad run ends delighted, finished, with the card gone", () => {
    const s = reduceAll(parseJsonl(notepadRun));
    expect(s.mood).toBe("delighted");
    expect(s.runs.RUN1).toMatchObject({
      status: "finished",
      result: "ok",
      request: "open Notepad",
    });
    expect(s.pendingApprovals).toEqual([]);
    expect(s.runs.RUN1.costInr).toBeCloseTo(0.4);
  });
});

describe("parseJsonl", () => {
  it("skips blank lines and rejects lines that are not events", () => {
    const line =
      '{"id":"1","run_id":"r","ts":"t","type":"mood","title":"x","payload":{}}';
    expect(parseJsonl(`\n${line}\n\n`)).toHaveLength(1);
    expect(() => parseJsonl("not json")).toThrow(/line 1/);
    expect(() => parseJsonl('{"hello":1}')).toThrow(/line 1/);
  });
});
