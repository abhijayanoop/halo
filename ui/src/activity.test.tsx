import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { CollapsedBar } from "./components/CollapsedBar";
import { moodSpec } from "./character/spec";
import { type HaloState, type RunView, initialState } from "./state/reducer";

const run = (status: RunView["status"]): RunView => ({
  id: "R1",
  request: "open Notepad",
  status,
  startedAt: "2026-10-17T10:00:00.000Z",
  timeline: [],
  openSteps: [],
  progress: null,
  agents: {},
  costInr: 0,
});

const withRun = (r: RunView, mood: HaloState["mood"]): HaloState => ({
  ...initialState,
  mood,
  activeRunId: r.id,
  runs: { [r.id]: r },
  order: [r.id],
});

describe("the activity light on the minimised bar", () => {
  it("blinks while a run is working, in the colour of the mood", () => {
    render(
      <CollapsedBar halo={withRun(run("running"), "thinking")} onExpand={() => {}} />,
    );
    const light = screen.getByTestId("activity-light");
    expect(light).toHaveAttribute("data-color", moodSpec("thinking").ring);
    expect(light).toHaveAttribute("data-blinking", "true");
  });

  it("changes colour as the mood changes", () => {
    const { rerender } = render(
      <CollapsedBar halo={withRun(run("running"), "thinking")} onExpand={() => {}} />,
    );
    rerender(
      <CollapsedBar halo={withRun(run("running"), "focused")} onExpand={() => {}} />,
    );
    expect(screen.getByTestId("activity-light")).toHaveAttribute(
      "data-color",
      moodSpec("focused").ring,
    );
  });

  it("is also lit while Halo waits for an answer", () => {
    render(
      <CollapsedBar halo={withRun(run("paused"), "asking")} onExpand={() => {}} />,
    );
    expect(screen.getByTestId("activity-light")).toHaveAttribute(
      "data-color",
      moodSpec("asking").ring,
    );
  });

  it("is off when nothing is running or the run is over", () => {
    const { rerender } = render(
      <CollapsedBar halo={initialState} onExpand={() => {}} />,
    );
    expect(screen.queryByTestId("activity-light")).toBeNull();
    rerender(
      <CollapsedBar halo={withRun(run("finished"), "idle")} onExpand={() => {}} />,
    );
    expect(screen.queryByTestId("activity-light")).toBeNull();
  });
});

describe("the scrollbars", () => {
  const css = readFileSync("src/index.css", "utf8");

  it("are dark and thin instead of the system white", () => {
    expect(css).toContain("scrollbar-color");
    expect(css).toContain("scrollbar-width: thin");
  });

  it("tell the browser the page is dark, so native controls follow", () => {
    expect(css).toContain("color-scheme: dark");
  });
});
