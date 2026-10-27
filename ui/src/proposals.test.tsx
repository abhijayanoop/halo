import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { Api } from "./api";
import { Panel } from "./components/Panel";
import { initialState, reduce } from "./state/reducer";
import type { HaloEvent } from "./types/generated/HaloEvent";

let n = 0;
const ev = (
  type: HaloEvent["type"],
  payload: Record<string, unknown> = {},
): HaloEvent => {
  n += 1;
  return {
    id: `W${String(n).padStart(4, "0")}`,
    run_id: "R1",
    ts: new Date(Date.UTC(2026, 9, 27, 10, 0, 0, n * 100)).toISOString(),
    type,
    title: `${type} title`,
    payload,
  };
};

const proposals = [
  {
    title: "Continue: Add rate limiting",
    project: "halo",
    request: "Add rate limiting in halo",
    source: "last_stop",
  },
  {
    title: "Write the Day 4 notes",
    project: null,
    request: "Write the Day 4 notes",
    source: "journal",
  },
];

const finished = (result: Record<string, unknown>) =>
  reduce(
    reduce(initialState, ev("run.started", { request: "let's get to work" })),
    ev("run.finished", {
      status: "ok",
      results: [{ step: 0, tool: "work.start", status: "ok", result }],
    }),
  );

describe("proposals in the reducer", () => {
  it("keeps the proposals of a work.start run", () => {
    const state = finished({ answer: "You stopped at: x.", proposals });
    expect(state.runs.R1.proposals).toEqual([
      {
        title: "Continue: Add rate limiting",
        project: "halo",
        request: "Add rate limiting in halo",
      },
      {
        title: "Write the Day 4 notes",
        project: null,
        request: "Write the Day 4 notes",
      },
    ]);
  });

  it("has none when the result has none, or they are malformed", () => {
    expect(finished({ answer: "hi" }).runs.R1.proposals).toBeUndefined();
    expect(
      finished({ answer: "hi", proposals: "nope" }).runs.R1.proposals,
    ).toBeUndefined();
    const mixed = finished({
      answer: "hi",
      proposals: [
        { title: "ok", request: "do ok" },
        { title: 3 },
        null,
        { request: "no title" },
      ],
    });
    expect(mixed.runs.R1.proposals).toEqual([
      { title: "ok", project: null, request: "do ok" },
    ]);
  });

  it("shows at most three", () => {
    const many = Array.from({ length: 6 }, (_, i) => ({
      title: `t${i}`,
      request: `r${i}`,
    }));
    expect(
      finished({ answer: "x", proposals: many }).runs.R1.proposals,
    ).toHaveLength(3);
  });
});

describe("proposals in the panel", () => {
  let api: Api;
  beforeEach(() => {
    api = {
      run: vi.fn(async () => ({ runId: "R2" })),
      approve: vi.fn(),
    } as unknown as Api;
  });
  const halo = () => finished({ answer: "You stopped at: x.", proposals });

  it("shows each proposal as a button under the answer", () => {
    render(<Panel halo={halo()} api={api} onCollapse={() => {}} />);
    expect(screen.getByTestId("run-answer")).toHaveTextContent(
      "You stopped at",
    );
    const buttons = screen.getAllByTestId("proposal");
    expect(buttons).toHaveLength(2);
    expect(buttons[0]).toHaveTextContent("Continue: Add rate limiting");
  });

  it("clicking one starts a run with its request", async () => {
    render(<Panel halo={halo()} api={api} onCollapse={() => {}} />);
    await userEvent.click(screen.getAllByTestId("proposal")[1]);
    expect(api.run).toHaveBeenCalledWith("Write the Day 4 notes");
  });

  it("says so when the run could not be started", async () => {
    (api.run as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("down"),
    );
    render(<Panel halo={halo()} api={api} onCollapse={() => {}} />);
    await userEvent.click(screen.getAllByTestId("proposal")[0]);
    await waitFor(() =>
      expect(screen.getByText(/couldn't reach halo/i)).toBeInTheDocument(),
    );
  });

  it("shows text, not markup, for a title from a note", () => {
    const evil = '<img src=x onerror="alert(1)">';
    const state = finished({
      answer: "x",
      proposals: [{ title: evil, request: evil, project: null }],
    });
    const { container } = render(
      <Panel halo={state} api={api} onCollapse={() => {}} />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(screen.getByTestId("proposal")).toHaveTextContent(evil);
  });

  it("shows no proposal buttons for an ordinary answer", () => {
    render(
      <Panel
        halo={finished({ reply: "hi" })}
        api={api}
        onCollapse={() => {}}
      />,
    );
    expect(screen.queryByTestId("proposal")).toBeNull();
  });
});
