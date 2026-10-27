import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Panel } from "./components/Panel";
import { PermissionCard } from "./components/PermissionCard";
import { initialState } from "./state/reducer";

const api = { run: vi.fn(), approve: vi.fn() };

describe("the panel rail", () => {
  it("reminds you what you asked", () => {
    const halo = {
      ...initialState,
      activeRunId: "R1",
      order: ["R1"],
      runs: {
        R1: {
          id: "R1",
          request: "open Notepad and write a note",
          status: "running" as const,
          startedAt: "2026-10-17T10:00:00.000Z",
          timeline: [],
          openSteps: [],
          progress: null,
          agents: {},
          costInr: 0,
        },
      },
    };
    render(<Panel halo={halo} api={api} onCollapse={() => {}} />);
    expect(screen.getByTestId("run-request")).toHaveTextContent(
      "open Notepad and write a note",
    );
  });

  it("shows no request when nothing has been asked", () => {
    render(<Panel halo={initialState} api={api} onCollapse={() => {}} />);
    expect(screen.queryByTestId("run-request")).toBeNull();
  });
});

describe("the card detail", () => {
  it("wraps at word boundaries, never in the middle of a word", () => {
    render(
      <PermissionCard
        approval={{
          approvalId: "A1",
          runId: "R1",
          action: "app.open",
          detail: "Notepad is not on your allowlist. Open it once?",
          risk: "medium",
          stepIndex: 0,
          requestedAt: "2026-10-17T10:00:00.000Z",
        }}
        total={1}
        api={api}
      />,
    );
    const cls = screen.getByTestId("card-detail").className;
    expect(cls).not.toContain("break-all");
    expect(cls).toContain("break-words");
  });
});
