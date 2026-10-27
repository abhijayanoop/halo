import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { type Api, createApi } from "./api";
import { Panel } from "./components/Panel";
import { type HaloState, initialState, reduce } from "./state/reducer";
import type { HaloEvent } from "./types/generated/HaloEvent";

let n = 0;
const ev = (
  type: HaloEvent["type"],
  payload: Record<string, unknown> = {},
  extra: Partial<HaloEvent> = {},
): HaloEvent => {
  n += 1;
  return {
    id: `M${String(n).padStart(4, "0")}`,
    run_id: "memory",
    ts: new Date(Date.UTC(2026, 9, 17, 10, 0, 0, n * 100)).toISOString(),
    type,
    title: `${type} title`,
    payload,
    ...extra,
  };
};

const proposed = (id: string, fact: string, extra = {}) =>
  ev("memory.proposed", {
    candidate_id: id,
    fact,
    subject: "halo",
    source: "agent",
    trust: "medium",
    ...extra,
  });

describe("proposed memories in the reducer", () => {
  it("collects proposals from memory.proposed events", () => {
    const state = reduce(initialState, proposed("^p-1", "Prefers pytest"));
    expect(state.proposedMemories).toEqual([
      {
        candidateId: "^p-1",
        fact: "Prefers pytest",
        subject: "halo",
        source: "agent",
        trust: "medium",
      },
    ]);
  });

  it("does not list the same proposal twice", () => {
    let state = reduce(initialState, proposed("^p-1", "Prefers pytest"));
    state = reduce(state, proposed("^p-1", "Prefers pytest"));
    expect(state.proposedMemories).toHaveLength(1);
  });

  it("drops a proposal once it is saved or discarded", () => {
    let state = reduce(initialState, proposed("^p-1", "one"));
    state = reduce(state, proposed("^p-2", "two"));
    state = reduce(
      state,
      ev("memory.saved", { candidate_id: "^p-1", fact: "one" }),
    );
    expect(state.proposedMemories.map((p) => p.candidateId)).toEqual(["^p-2"]);
    state = reduce(
      state,
      ev("memory.forgotten", { candidate_id: "^p-2", rejected: true }),
    );
    expect(state.proposedMemories).toEqual([]);
  });

  it("a memory saved by the remember skill does not touch the proposals", () => {
    let state = reduce(initialState, proposed("^p-1", "one"));
    state = reduce(state, ev("memory.saved", { fact: "x" }, { run_id: "R9" }));
    expect(state.proposedMemories).toHaveLength(1);
  });

  it("proposals belong to no run: no run appears and nothing else changes", () => {
    const state = reduce(initialState, proposed("^p-1", "one"));
    expect(state.runs).toEqual({});
    expect(state.activeRunId).toBeNull();
    expect(state.mood).toBe("idle");
    expect(state.statusLine).toBe(initialState.statusLine);
  });

  it("ignores a proposal with no id or no fact", () => {
    let state: HaloState = reduce(
      initialState,
      ev("memory.proposed", { fact: "x" }),
    );
    state = reduce(state, ev("memory.proposed", { candidate_id: "^p-3" }));
    expect(state.proposedMemories).toEqual([]);
  });
});

describe("recalled memories on the timeline", () => {
  it("keeps the exact memories that went into a prompt", () => {
    const state = reduce(
      initialState,
      ev(
        "tool.result",
        {
          stage: "memory",
          memories: [
            {
              fact: "I picked pywebview",
              note: "Projects/halo.md",
              source: "you",
              trust: "high",
            },
          ],
        },
        { run_id: "R1", title: "Recalled 1 memory" },
      ),
    );
    const item = state.runs.R1.timeline[0];
    expect(item.memories).toEqual([
      {
        fact: "I picked pywebview",
        note: "Projects/halo.md",
        source: "you",
        trust: "high",
      },
    ]);
  });

  it("a timeline item without memories has none", () => {
    const state = reduce(
      initialState,
      ev("step.started", { stage: "route" }, { run_id: "R1" }),
    );
    expect(state.runs.R1.timeline[0].memories).toBeUndefined();
  });
});

describe("the api client", () => {
  const sent = async (call: (api: Api) => Promise<unknown> | undefined) => {
    const fetchFn = vi.fn(
      async () => new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    const api = createApi(
      "http://127.0.0.1:8765",
      "tok",
      fetchFn as unknown as typeof fetch,
    );
    await call(api);
    const [url, init] = fetchFn.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    return { url, body: JSON.parse(String(init.body)) };
  };

  it("approves a proposal", async () => {
    const r = await sent((api) => api.memoryApprove?.("^p-1"));
    expect(r.url).toBe("http://127.0.0.1:8765/memory/approve");
    expect(r.body).toEqual({ candidate_id: "^p-1" });
  });

  it("approves into a chosen note", async () => {
    const r = await sent((api) => api.memoryApprove?.("^p-1", "People/sam.md"));
    expect(r.body).toEqual({ candidate_id: "^p-1", note: "People/sam.md" });
  });

  it("rejects a proposal", async () => {
    const r = await sent((api) => api.memoryReject?.("^p-1"));
    expect(r.url).toBe("http://127.0.0.1:8765/memory/reject");
    expect(r.body).toEqual({ candidate_id: "^p-1" });
  });
});

describe("the Memory tab", () => {
  const apiWith = (): Api => ({
    run: vi.fn(),
    approve: vi.fn(async () => {}),
    memoryApprove: vi.fn(async () => {}),
    memoryReject: vi.fn(async () => {}),
  });
  const withProposals = (): HaloState => {
    let s = reduce(
      initialState,
      proposed("^p-1", "Prefers pytest over unittest"),
    );
    s = reduce(
      s,
      proposed("^p-2", "Uses ruff", { source: "agent", trust: "low" }),
    );
    return s;
  };
  const open = async (halo: HaloState, api: Api) => {
    render(<Panel halo={halo} api={api} onCollapse={() => {}} />);
    await userEvent.click(screen.getByRole("tab", { name: /memory/i }));
  };

  it("lists what Halo thinks is worth remembering, with where it came from", async () => {
    await open(withProposals(), apiWith());
    const rows = screen.getAllByTestId("proposed-memory");
    expect(rows).toHaveLength(2);
    expect(
      within(rows[0]).getByText(/prefers pytest over unittest/i),
    ).toBeInTheDocument();
    expect(within(rows[0]).getByText(/halo/)).toBeInTheDocument();
    expect(within(rows[0]).getByText(/agent/i)).toBeInTheDocument();
  });

  it("approves one proposal", async () => {
    const api = apiWith();
    await open(withProposals(), api);
    const first = screen.getAllByTestId("proposed-memory")[0];
    await userEvent.click(
      within(first).getByRole("button", { name: /approve/i }),
    );
    expect(api.memoryApprove).toHaveBeenCalledWith("^p-1");
  });

  it("rejects one proposal", async () => {
    const api = apiWith();
    await open(withProposals(), api);
    const second = screen.getAllByTestId("proposed-memory")[1];
    await userEvent.click(
      within(second).getByRole("button", { name: /reject/i }),
    );
    expect(api.memoryReject).toHaveBeenCalledWith("^p-2");
  });

  it("says so when nothing is waiting", async () => {
    await open(initialState, apiWith());
    expect(screen.queryAllByTestId("proposed-memory")).toHaveLength(0);
    expect(screen.getByText(/nothing waiting/i)).toBeInTheDocument();
  });

  it("shows how many proposals are waiting on the tab", () => {
    render(
      <Panel halo={withProposals()} api={apiWith()} onCollapse={() => {}} />,
    );
    expect(screen.getByRole("tab", { name: /memory/i })).toHaveTextContent("2");
  });

  it("says so if the answer did not go through", async () => {
    const api = apiWith();
    api.memoryApprove = vi.fn(async () => {
      throw new Error("nope");
    });
    await open(withProposals(), api);
    const first = screen.getAllByTestId("proposed-memory")[0];
    await userEvent.click(
      within(first).getByRole("button", { name: /approve/i }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /didn't go through/i,
    );
  });
});

describe("the Now tab shows what went into the prompt", () => {
  it("lists the recalled memories under the step", () => {
    const halo = reduce(
      reduce(
        initialState,
        ev("run.started", { request: "what did I pick?" }, { run_id: "R1" }),
      ),
      ev(
        "tool.result",
        {
          stage: "memory",
          memories: [
            {
              fact: "I picked pywebview",
              note: "Projects/halo.md",
              source: "you",
              trust: "high",
            },
          ],
        },
        { run_id: "R1", title: "Recalled 1 memory" },
      ),
    );
    render(
      <Panel
        halo={halo}
        api={{ run: vi.fn(), approve: vi.fn() }}
        onCollapse={() => {}}
      />,
    );
    expect(screen.getByText("I picked pywebview")).toBeInTheDocument();
    expect(screen.getByText(/Projects\/halo\.md/)).toBeInTheDocument();
  });
});
