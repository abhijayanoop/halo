import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  MOODS,
  initialState,
  parseJsonl,
  reduce,
} from "./state/reducer";

// The scripted tour (public/demo/tour.jsonl) is how the animations are shown
// without calling a model. It must keep working as the reducer changes.
const events = parseJsonl(readFileSync("public/demo/tour.jsonl", "utf8"));

describe("the demo tour", () => {
  it("is a valid recording with unique ids and gaps the replay can follow", () => {
    expect(events.length).toBeGreaterThan(30);
    expect(new Set(events.map((e) => e.id)).size).toBe(events.length);
    for (let i = 1; i < events.length; i++) {
      const gap = Date.parse(events[i].ts) - Date.parse(events[i - 1].ts);
      expect(gap).toBeGreaterThanOrEqual(0);
      expect(gap).toBeLessThanOrEqual(3500);
    }
  });

  it("visits all 13 moods", () => {
    const seen = new Set<string>();
    let state = initialState;
    for (const e of events) {
      state = reduce(state, e);
      seen.add(state.mood);
    }
    expect([...seen].sort()).toEqual([...MOODS].sort());
  });

  it("ends calm: idle, no open card, the first run answered, the second failed", () => {
    const state = events.reduce(reduce, initialState);
    expect(state.mood).toBe("idle");
    expect(state.pendingApprovals).toEqual([]);
    expect(state.runs.R1.status).toBe("finished");
    expect(state.runs.R1.answer).toContain("Morning plan");
    expect(state.runs.R2.status).toBe("failed");
    expect(state.proposedMemories.map((p) => p.candidateId)).toEqual(["^p-tour1"]);
  });

  it("shows the permission card for a while, then clears it", () => {
    let state = initialState;
    let cardSeen = false;
    for (const e of events) {
      state = reduce(state, e);
      if (state.pendingApprovals.length > 0) cardSeen = true;
    }
    expect(cardSeen).toBe(true);
  });

  it("lights helpers while they run", () => {
    let state = initialState;
    let most = 0;
    for (const e of events) {
      state = reduce(state, e);
      const run = state.activeRunId ? state.runs[state.activeRunId] : undefined;
      const running = run
        ? Object.values(run.agents).filter((a) => a.status === "running").length
        : 0;
      most = Math.max(most, running);
    }
    expect(most).toBe(2);
  });
});
