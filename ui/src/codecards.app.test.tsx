import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { useStore } from "./state/store";
import type { HaloEvent } from "./types/generated/HaloEvent";

vi.mock("./useHaloEvents", () => ({ useHaloEvents: () => {} }));

let n = 0;
const ev = (
  type: HaloEvent["type"],
  payload: Record<string, unknown> = {},
): HaloEvent => {
  n += 1;
  return {
    id: `A${String(n).padStart(4, "0")}`,
    run_id: "R1",
    ts: new Date(Date.UTC(2026, 9, 27, 10, 0, 0, n * 100)).toISOString(),
    type,
    title: `${type} title`,
    payload,
  };
};

const fetchMock = vi.fn(async () => new Response("{}", { status: 200 }));

beforeEach(() => {
  fetchMock.mockClear();
  vi.stubGlobal("fetch", fetchMock);
  window.history.pushState({}, "", "/#token=tok123");
  useStore.setState({ ...useStore.getInitialState(), expanded: false });
});
afterEach(() => vi.unstubAllGlobals());

const base = { step_index: 0, project: "halo" };
const brief = {
  ...base,
  approval_id: "B1",
  action: "Start coding task",
  detail: "Add rate limiting",
  risk: "medium",
  kind: "code.brief",
  mode: "implement",
  brief: {
    goal: "Add rate limiting",
    acceptance_criteria: ["429 over the limit"],
    likely_files: [],
    test_cmd: "uv run pytest -q",
    constraints: [],
    out_of_scope: [],
  },
};
const result = {
  ...base,
  approval_id: "X1",
  action: "Review the result",
  detail: "Added it",
  risk: "high",
  kind: "code.result",
  iteration: 1,
  can_iterate: true,
  notice: "",
  cost_inr: "11.40",
  branch: "halo/x",
  worktree: "C:/x",
  status: "done",
  summary: "Added it",
  tests: { passed: true, exit_code: 0, timed_out: false, tail: "ok" },
  review: { result: "pass", summary: "fine", issues: [] },
  diff_stat: "1 file changed",
  changed_files: ["a.py"],
};

const ask = (payload: Record<string, unknown>) =>
  act(() => {
    useStore
      .getState()
      .apply(ev("run.started", { request: "add rate limiting" }));
    useStore.getState().apply(ev("approval.requested", payload));
  });

describe("the code cards in the app", () => {
  it("shows the brief card instead of the bar and posts the answer to /code/decision", async () => {
    render(<App />);
    ask(brief);
    expect(screen.getByLabelText(/goal/i)).toHaveValue("Add rate limiting");
    await userEvent.click(screen.getByRole("button", { name: /start/i }));
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toMatch(/\/code\/decision$/);
    expect((init.headers as Record<string, string>)["X-Halo-Token"]).toBe(
      "tok123",
    );
    expect(JSON.parse(init.body as string)).toEqual({
      run_id: "R1",
      approval_id: "B1",
      action: "approve",
    });
  });

  it("shows the result card and never posts to /approve for it", async () => {
    render(<App />);
    ask(result);
    expect(screen.getByTestId("result-tests")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /discard/i }));
    const [url] = fetchMock.mock.calls[0] as unknown as [string];
    expect(url).toMatch(/\/code\/decision$/);
    expect(url).not.toMatch(/\/approve$/);
  });

  it("a plain permission request still uses the small card and /approve", async () => {
    render(<App />);
    ask({
      approval_id: "P1",
      action: "app.open",
      detail: "Notepad",
      risk: "medium",
      step_index: 0,
    });
    await userEvent.click(screen.getByRole("button", { name: /allow once/i }));
    const [url] = fetchMock.mock.calls[0] as unknown as [string];
    expect(url).toMatch(/\/approve$/);
  });

  it("the card goes away when the core resolves it", () => {
    render(<App />);
    ask(brief);
    act(() => {
      useStore
        .getState()
        .apply(
          ev("approval.resolved", { approval_id: "B1", grant: "allow_once" }),
        );
    });
    expect(screen.queryByLabelText(/goal/i)).toBeNull();
  });
});
