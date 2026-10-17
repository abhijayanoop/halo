import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";
import { MOODS } from "./state/reducer";
import { useStore } from "./state/store";
import type { HaloEvent } from "./types/generated/HaloEvent";

// The live connection is out of scope here: the store is fed directly.
vi.mock("./useHaloEvents", () => ({ useHaloEvents: () => {} }));

let n = 0;
const ev = (
  type: HaloEvent["type"],
  payload: Record<string, unknown> = {},
  extra: Partial<HaloEvent> = {},
): HaloEvent => {
  n += 1;
  return {
    id: `A${String(n).padStart(4, "0")}`,
    run_id: "R1",
    ts: new Date(Date.UTC(2026, 9, 12, 10, 0, 0, n * 100)).toISOString(),
    type,
    title: `${type} title`,
    payload,
    ...extra,
  };
};

const resize = vi.fn();

beforeEach(() => {
  resize.mockClear();
  (window as unknown as { pywebview: unknown }).pywebview = { api: { resize } };
  window.history.pushState({}, "", "/");
  useStore.setState({ ...useStore.getInitialState(), expanded: false });
});

afterEach(() => {
  delete (window as unknown as { pywebview?: unknown }).pywebview;
});

describe("App", () => {
  it("starts as the collapsed bar at 260 x 44", () => {
    render(<App />);
    expect(
      screen.getByRole("button", { name: /open halo/i }),
    ).toBeInTheDocument();
    expect(resize).toHaveBeenLastCalledWith(260, 44);
  });

  it("opens the panel on click (640 x 360) and collapses on Escape", async () => {
    render(<App />);
    await userEvent.click(screen.getByRole("button", { name: /open halo/i }));
    expect(screen.getByRole("tablist")).toBeInTheDocument();
    expect(resize).toHaveBeenLastCalledWith(640, 360);

    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("tablist")).toBeNull();
    expect(resize).toHaveBeenLastCalledWith(260, 44);
  });

  it("grows to the permission-card size the moment an approval is requested", () => {
    render(<App />);
    act(() => {
      useStore.getState().apply(ev("run.started", { request: "open Notepad" }));
      useStore.getState().apply(
        ev("approval.requested", {
          approval_id: "AP1",
          action: "app.open",
          detail: "{'app': 'Notepad'}",
          risk: "medium",
        }),
      );
    });
    expect(resize).toHaveBeenLastCalledWith(380, 140);
  });

  it("works in a plain browser with no pywebview bridge", () => {
    delete (window as unknown as { pywebview?: unknown }).pywebview;
    expect(() => render(<App />)).not.toThrow();
  });

  it("shows the mood the core sent, not one the UI made up", () => {
    render(<App />);
    act(() => {
      useStore.getState().apply(ev("mood", { mood: "guarding" }));
    });
    expect(screen.getByRole("img")).toHaveAttribute("data-mood", "guarding");
  });
});

describe("/moods", () => {
  it("shows all 13 moods side by side with their labels and ring colours", () => {
    window.history.pushState({}, "", "/moods");
    render(<App />);
    const figures = screen.getAllByTestId("mood-figure");
    expect(figures.map((f) => f.getAttribute("data-mood"))).toEqual([...MOODS]);
    expect(screen.getByTestId("mood-figure-asking")).toHaveTextContent(
      "Asking",
    );
    expect(screen.getByTestId("mood-figure-asking")).toHaveTextContent(
      "#ffb020",
    );
  });
});
