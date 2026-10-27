import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Api } from "./api";
import { CollapsedBar } from "./components/CollapsedBar";
import { Panel } from "./components/Panel";
import { SIZES, selectView } from "./view";
import { type HaloState, initialState, reduceAll } from "./state/reducer";
import type { HaloEvent } from "./types/generated/HaloEvent";

let n = 0;
const ev = (
  type: HaloEvent["type"],
  payload: Record<string, unknown> = {},
  extra: Partial<HaloEvent> = {},
): HaloEvent => {
  n += 1;
  return {
    id: `H${String(n).padStart(4, "0")}`,
    run_id: "R1",
    ts: new Date(Date.UTC(2026, 9, 12, 10, 0, 0, n * 500)).toISOString(),
    type,
    title: `${type} title`,
    payload,
    ...extra,
  };
};

const running = (): HaloState =>
  reduceAll([
    ev("run.started", { request: "plan a trip" }),
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
    ev("step.started", { step: 2, of: 3 }, { title: "Comparing hotels" }),
  ]);

describe("selectView", () => {
  it("is the collapsed bar by default and the panel once expanded", () => {
    expect(selectView(initialState, false)).toBe("bar");
    expect(selectView(initialState, true)).toBe("panel");
  });

  it("is the permission card whenever an approval is pending, expanded or not", () => {
    const asked = reduceAll([
      ev("run.started", { request: "x" }),
      ev("approval.requested", {
        approval_id: "A",
        action: "a",
        detail: "",
        risk: "medium",
      }),
    ]);
    expect(selectView(asked, false)).toBe("card");
    expect(selectView(asked, true)).toBe("card");
  });

  it("uses the agreed window sizes", () => {
    expect(SIZES.bar).toEqual([260, 44]);
    expect(SIZES.card).toEqual([380, 140]);
    expect(SIZES.panel).toEqual([640, 360]);
  });
});

describe("CollapsedBar", () => {
  it("shows the status line, step progress and one dot per running agent", () => {
    render(<CollapsedBar halo={running()} onExpand={() => {}} />);
    expect(screen.getByTestId("status-line")).toHaveTextContent(
      "Comparing hotels",
    );
    expect(screen.getByTestId("step-progress")).toHaveTextContent("2/3");
    expect(screen.getAllByTestId("agent-dot")).toHaveLength(2);
  });

  it("shows Ready and no progress or dots when nothing is running", () => {
    render(<CollapsedBar halo={initialState} onExpand={() => {}} />);
    expect(screen.getByTestId("status-line")).toHaveTextContent("Ready");
    expect(screen.queryByTestId("step-progress")).toBeNull();
    expect(screen.queryAllByTestId("agent-dot")).toHaveLength(0);
  });

  it("does not count finished agents", () => {
    const halo = reduceAll(
      [ev("agent.finished", {}, { agent_id: "a2" })],
      running(),
    );
    render(<CollapsedBar halo={halo} onExpand={() => {}} />);
    expect(screen.getAllByTestId("agent-dot")).toHaveLength(1);
  });

  it("draws the mascot in the mood the core decided", () => {
    const halo = reduceAll([ev("mood", { mood: "thinking" })]);
    render(<CollapsedBar halo={halo} onExpand={() => {}} />);
    expect(screen.getByRole("img")).toHaveAttribute("data-mood", "thinking");
  });

  it("expands when clicked", async () => {
    const onExpand = vi.fn();
    render(<CollapsedBar halo={initialState} onExpand={onExpand} />);
    await userEvent.click(screen.getByRole("button", { name: /open halo/i }));
    expect(onExpand).toHaveBeenCalledOnce();
  });
});

describe("Panel", () => {
  let api: Api;
  beforeEach(() => {
    api = {
      run: vi.fn(async () => ({ runId: "R9" })),
      approve: vi.fn(async () => {}),
    };
  });

  it("lists the timeline in order with step durations", () => {
    const halo = reduceAll([
      ev("run.started", { request: "x" }),
      ev("step.started", {}, { title: "Planning" }),
      ev("step.finished", {}, { title: "Plan ready" }),
    ]);
    render(<Panel halo={halo} api={api} onCollapse={() => {}} />);
    const items = screen
      .getAllByTestId("timeline-item")
      .map((el) => el.textContent ?? "");
    expect(items[0]).toContain("run.started title");
    expect(items[1]).toContain("Planning");
    expect(items[1]).toContain("500 ms");
  });

  it("draws the agent tree indented by depth", () => {
    render(<Panel halo={running()} api={api} onCollapse={() => {}} />);
    const nodes = screen.getAllByTestId("agent-node");
    expect(nodes.map((el) => el.getAttribute("data-depth"))).toEqual([
      "0",
      "1",
    ]);
    expect(nodes[1]).toHaveTextContent("Reader");
  });

  it("sends the typed request to the core and clears the box", async () => {
    render(<Panel halo={initialState} api={api} onCollapse={() => {}} />);
    const box = screen.getByRole("textbox");
    await userEvent.type(box, "open Notepad{Enter}");
    expect(api.run).toHaveBeenCalledWith("open Notepad");
    await waitFor(() => expect(box).toHaveValue(""));
  });

  it("does not send an empty request", async () => {
    render(<Panel halo={initialState} api={api} onCollapse={() => {}} />);
    await userEvent.type(screen.getByRole("textbox"), "   {Enter}");
    expect(api.run).not.toHaveBeenCalled();
  });

  it("says plainly when the core could not be reached", async () => {
    api = { ...api, run: vi.fn(async () => Promise.reject(new Error("down"))) };
    render(<Panel halo={initialState} api={api} onCollapse={() => {}} />);
    await userEvent.type(screen.getByRole("textbox"), "hi{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /couldn't reach halo/i,
    );
  });

  it("has the five tabs, with the later ones stubbed", async () => {
    render(<Panel halo={initialState} api={api} onCollapse={() => {}} />);
    const tabs = screen.getAllByRole("tab").map((t) => t.textContent);
    expect(tabs).toEqual(["Now", "Approvals", "Memory", "Ledger", "History"]);
    await userEvent.click(screen.getByRole("tab", { name: "Ledger" }));
    expect(screen.getByTestId("tab-stub")).toHaveTextContent(/soon/i);
  });

  it("collapses from its button", async () => {
    const onCollapse = vi.fn();
    render(<Panel halo={initialState} api={api} onCollapse={onCollapse} />);
    await userEvent.click(screen.getByRole("button", { name: /collapse/i }));
    expect(onCollapse).toHaveBeenCalledOnce();
  });

  it("shows what the run has cost so far", () => {
    const halo = reduceAll([
      ev("run.started", { request: "x" }),
      ev("cost.updated", { cost_inr: "1.25" }),
    ]);
    render(<Panel halo={halo} api={api} onCollapse={() => {}} />);
    expect(screen.getByTestId("run-cost")).toHaveTextContent("₹1.25");
  });
});

describe("keyboard", () => {
  it("fires Escape on the document (the App uses it to collapse)", () => {
    const seen = vi.fn();
    document.addEventListener("keydown", seen);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(seen).toHaveBeenCalled();
  });
});
