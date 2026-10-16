import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { Api } from "../api";
import {
  type HaloState,
  type PendingApproval,
  type RunView,
  initialState,
} from "../state/reducer";
import { CollapsedBar } from "./CollapsedBar";
import { Panel } from "./Panel";
import { PermissionCard } from "./PermissionCard";

const run = (extra: Partial<RunView> = {}): RunView => ({
  id: "R1",
  request: "open Notepad",
  status: "running",
  startedAt: "2026-10-17T10:00:00.000Z",
  timeline: [],
  openSteps: [],
  progress: null,
  agents: {},
  costInr: 0,
  ...extra,
});

const withRun = (r: RunView, extra: Partial<HaloState> = {}): HaloState => ({
  ...initialState,
  activeRunId: r.id,
  runs: { [r.id]: r },
  order: [r.id],
  ...extra,
});

describe("CollapsedBar (v2)", () => {
  it("tints the pill with the ring colour of the current mood", () => {
    render(
      <CollapsedBar
        halo={{ ...initialState, mood: "guarding" }}
        onExpand={() => {}}
      />,
    );
    const pill = screen.getByRole("button", { name: /open halo/i });
    expect(pill).toHaveAttribute("data-mood", "guarding");
    expect(pill.style.getPropertyValue("--ring").toLowerCase()).toBe("#ff4d5e");
  });

  it("lets the eyes follow the pointer and rest when it leaves", () => {
    const { container } = render(
      <CollapsedBar halo={initialState} onExpand={() => {}} />,
    );
    const eyes = () => container.querySelector('[data-layer="eyes"]');
    fireEvent.mouseMove(document, { clientX: 400, clientY: 0 });
    expect(Number(eyes()?.getAttribute("data-gaze-x"))).toBeGreaterThan(0);
    fireEvent.mouseMove(document, { clientX: -400, clientY: 0 });
    expect(Number(eyes()?.getAttribute("data-gaze-x"))).toBeLessThan(0);
    fireEvent.mouseLeave(document.body);
    fireEvent(document, new Event("mouseleave"));
    expect(Number(eyes()?.getAttribute("data-gaze-x"))).toBe(0);
  });

  it("shows step progress as a bar while a run is live, and no bar otherwise", () => {
    const live = withRun(run({ progress: { step: 1, of: 3 } }));
    const { rerender } = render(
      <CollapsedBar halo={live} onExpand={() => {}} />,
    );
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "1");
    expect(bar).toHaveAttribute("aria-valuemax", "3");
    rerender(<CollapsedBar halo={initialState} onExpand={() => {}} />);
    expect(screen.queryByRole("progressbar")).toBeNull();
  });
});

describe("PermissionCard (v2)", () => {
  const approval = (risk: PendingApproval["risk"]): PendingApproval => ({
    approvalId: "AP1",
    runId: "R1",
    action: "app.open",
    detail: "{'app': 'Notepad'}",
    risk,
    stepIndex: 0,
    requestedAt: "2026-10-17T10:00:00.000Z",
  });
  const api: Api = { run: vi.fn(), approve: vi.fn(async () => {}) };

  it("styles the card by risk, so a high-risk ask looks different at a glance", () => {
    const { rerender } = render(
      <PermissionCard approval={approval("low")} total={1} api={api} />,
    );
    const card = () => screen.getByRole("region", { name: /permission/i });
    expect(card()).toHaveAttribute("data-risk", "low");
    rerender(
      <PermissionCard approval={approval("high")} total={1} api={api} />,
    );
    expect(card()).toHaveAttribute("data-risk", "high");
  });
});

describe("Panel Now tab (v2)", () => {
  const api: Api = { run: vi.fn(), approve: vi.fn(async () => {}) };

  it("marks each timeline step as running, done or failed", () => {
    const halo = withRun(
      run({
        timeline: [
          {
            id: "T1",
            type: "step.started",
            title: "Open Notepad",
            ts: "2026-10-17T10:00:01.000Z",
            agentId: null,
            durationMs: 800,
            stepStatus: "ok",
          },
          {
            id: "T2",
            type: "step.started",
            title: "Write note",
            ts: "2026-10-17T10:00:02.000Z",
            agentId: null,
            durationMs: 300,
            stepStatus: "error",
          },
          {
            id: "T3",
            type: "step.started",
            title: "Save",
            ts: "2026-10-17T10:00:03.000Z",
            agentId: null,
          },
        ],
        openSteps: ["T3"],
      }),
    );
    render(<Panel halo={halo} api={api} onCollapse={() => {}} />);
    const items = screen.getAllByTestId("timeline-item");
    expect(items.map((i) => i.getAttribute("data-status"))).toEqual([
      "done",
      "failed",
      "running",
    ]);
  });

  it("shows how many helpers are running in the header", () => {
    const halo = withRun(
      run({
        agents: {
          A1: { id: "A1", parentId: null, title: "Search", status: "running" },
          A2: { id: "A2", parentId: null, title: "Read", status: "running" },
        },
      }),
    );
    render(<Panel halo={halo} api={api} onCollapse={() => {}} />);
    expect(screen.getByTestId("helper-count")).toHaveTextContent("2");
  });
});
