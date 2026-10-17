import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Panel } from "./components/Panel";
import { initialState, reduce } from "./state/reducer";
import type { HaloEvent } from "./types/generated/HaloEvent";

let n = 0;
const ev = (
  type: HaloEvent["type"],
  payload: Record<string, unknown> = {},
  run_id = "R1",
): HaloEvent => {
  n += 1;
  return {
    id: `A${String(n).padStart(4, "0")}`,
    run_id,
    ts: new Date(Date.UTC(2026, 9, 17, 10, 0, 0, n * 100)).toISOString(),
    type,
    title: `${type} title`,
    payload,
  };
};

const finished = (results: unknown[]) =>
  ev("run.finished", { status: "ok", results });

const start = () =>
  reduce(initialState, ev("run.started", { request: "who are you?" }));

describe("the answer to a request", () => {
  it("keeps the reply of a chat run", () => {
    const state = reduce(
      start(),
      finished([
        { step: 0, tool: "chat", status: "ok", result: { reply: "I am Halo." } },
      ]),
    );
    expect(state.runs.R1.answer).toBe("I am Halo.");
  });

  it("keeps the answer of a recall run", () => {
    const state = reduce(
      start(),
      finished([
        {
          step: 0,
          tool: "memory.recall",
          status: "ok",
          result: { answer: "From your notes:\n- I picked pywebview", sources: [] },
        },
      ]),
    );
    expect(state.runs.R1.answer).toContain("I picked pywebview");
  });

  it("takes the last answer when several steps produced one", () => {
    const state = reduce(
      start(),
      finished([
        { step: 0, tool: "chat", status: "ok", result: { reply: "first" } },
        { step: 1, tool: "chat", status: "ok", result: { reply: "second" } },
      ]),
    );
    expect(state.runs.R1.answer).toBe("second");
  });

  it("has no answer when no step produced text", () => {
    const state = reduce(
      start(),
      finished([
        { step: 0, tool: "app.open", status: "ok", result: { opened: true } },
      ]),
    );
    expect(state.runs.R1.answer).toBeUndefined();
  });

  it("ignores a blank or non-text reply", () => {
    const state = reduce(
      start(),
      finished([
        { step: 0, tool: "chat", status: "ok", result: { reply: "   " } },
        { step: 1, tool: "chat", status: "ok", result: { reply: 42 } },
      ]),
    );
    expect(state.runs.R1.answer).toBeUndefined();
  });

  it("does not break on a finished run with no results at all", () => {
    const state = reduce(start(), ev("run.finished", { status: "ok" }));
    expect(state.runs.R1.answer).toBeUndefined();
  });
});

describe("showing the answer in the panel", () => {
  const api = { run: vi.fn(), approve: vi.fn() };

  it("puts the answer at the top of the Now tab", () => {
    const halo = reduce(
      start(),
      finished([
        { step: 0, tool: "chat", status: "ok", result: { reply: "I am Halo, a desktop assistant." } },
      ]),
    );
    render(<Panel halo={halo} api={api} onCollapse={() => {}} />);
    expect(screen.getByTestId("run-answer")).toHaveTextContent(
      "I am Halo, a desktop assistant.",
    );
  });

  it("shows no answer block while the run is still working", () => {
    render(<Panel halo={start()} api={api} onCollapse={() => {}} />);
    expect(screen.queryByTestId("run-answer")).toBeNull();
  });

  it("tells you when the run failed, in plain words", () => {
    const halo = reduce(
      start(),
      ev("run.failed", { reason: "Couldn't reach the model service. Try again in a moment." }),
    );
    render(<Panel halo={halo} api={api} onCollapse={() => {}} />);
    expect(screen.getByTestId("run-failure")).toHaveTextContent(
      "Couldn't reach the model service",
    );
  });
});
