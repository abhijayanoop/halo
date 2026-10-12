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
  extra: Partial<HaloEvent> = {},
): HaloEvent => {
  n += 1;
  return {
    id: `C${String(n).padStart(4, "0")}`,
    run_id: "R1",
    ts: new Date(Date.UTC(2026, 9, 12, 10, 0, 0, n * 100)).toISOString(),
    type,
    title: `${type} title`,
    payload,
    ...extra,
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

const ask = () =>
  act(() => {
    useStore.getState().apply(ev("run.started", { request: "open Notepad" }));
    useStore.getState().apply(
      ev("approval.requested", {
        approval_id: "AP9",
        action: "app.open",
        detail: "{'app': 'Notepad'}",
        risk: "medium",
        step_index: 0,
      }),
    );
  });

describe("the permission card in the app", () => {
  it("replaces the bar when Halo asks, and shows what it wants to open", () => {
    render(<App />);
    ask();
    expect(screen.queryByRole("button", { name: /open halo/i })).toBeNull();
    expect(screen.getByTestId("card-detail")).toHaveTextContent("Notepad");
  });

  it("Enter posts the approval, with the token and the approval id", async () => {
    render(<App />);
    ask();
    await userEvent.keyboard("{Enter}");

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ];
    expect(url).toMatch(/\/approve$/);
    expect((init.headers as Record<string, string>)["X-Halo-Token"]).toBe(
      "tok123",
    );
    expect(JSON.parse(init.body as string)).toEqual({
      run_id: "R1",
      approval_id: "AP9",
      grant: "allow_once",
    });
  });

  it("Escape denies instead of collapsing the panel", async () => {
    render(<App />);
    ask();
    await userEvent.keyboard("{Escape}");
    expect(
      JSON.parse(
        (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1]
          .body as string,
      ).grant,
    ).toBe("deny");
  });

  it("goes back to the bar once the approval is resolved", () => {
    render(<App />);
    ask();
    act(() => {
      useStore
        .getState()
        .apply(
          ev("approval.resolved", { approval_id: "AP9", grant: "allow_once" }),
        );
    });
    expect(
      screen.getByRole("button", { name: /open halo/i }),
    ).toBeInTheDocument();
  });
});
