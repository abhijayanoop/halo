import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { type Api, createApi } from "./api";
import { Panel } from "./components/Panel";
import { type RunView, initialState } from "./state/reducer";

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

const live = (r: RunView) => ({
  ...initialState,
  activeRunId: r.id,
  runs: { [r.id]: r },
  order: [r.id],
});

describe("the api client", () => {
  it("posts /stop with the run id and the token", async () => {
    const fetchFn = vi.fn(
      async () =>
        new Response(JSON.stringify({ ok: true }), { status: 200 }),
    );
    const api = createApi(
      "http://127.0.0.1:8765",
      "tok",
      fetchFn as unknown as typeof fetch,
    );
    await api.stop?.("R1");
    const [url, init] = fetchFn.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toBe("http://127.0.0.1:8765/stop");
    expect(JSON.parse(String(init.body))).toEqual({ run_id: "R1" });
    expect((init.headers as Record<string, string>)["X-Halo-Token"]).toBe(
      "tok",
    );
  });
});

describe("Stop in the panel header", () => {
  const api = (): Api => ({
    run: vi.fn(),
    approve: vi.fn(async () => {}),
    stop: vi.fn(async () => {}),
  });

  it("stops the run that is working", async () => {
    const a = api();
    render(<Panel halo={live(run())} api={a} onCollapse={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(a.stop).toHaveBeenCalledWith("R1");
  });

  it("also stops a run that is waiting on a card", () => {
    render(
      <Panel
        halo={live(run({ status: "paused" }))}
        api={api()}
        onCollapse={() => {}}
      />,
    );
    expect(screen.getByRole("button", { name: /stop/i })).toBeInTheDocument();
  });

  it("is not shown when nothing is running or the run is over", () => {
    const { rerender } = render(
      <Panel halo={initialState} api={api()} onCollapse={() => {}} />,
    );
    expect(screen.queryByRole("button", { name: /stop/i })).toBeNull();
    rerender(
      <Panel
        halo={live(run({ status: "finished", result: "ok" }))}
        api={api()}
        onCollapse={() => {}}
      />,
    );
    expect(screen.queryByRole("button", { name: /stop/i })).toBeNull();
  });

  it("says so if Stop did not go through", async () => {
    const a = api();
    a.stop = vi.fn(async () => {
      throw new Error("nope");
    });
    render(<Panel halo={live(run())} api={a} onCollapse={() => {}} />);
    await userEvent.click(screen.getByRole("button", { name: /stop/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/stop/i);
  });
});
