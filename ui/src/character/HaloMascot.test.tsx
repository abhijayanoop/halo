import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MOODS } from "../state/reducer";
import { HaloMascot } from "./HaloMascot";
import { moodSpec } from "./spec";

const bodyPath = (container: HTMLElement) =>
  container.querySelector('[data-layer="body"] path')?.getAttribute("d");

describe("HaloMascot", () => {
  it("renders every mood without crashing and labels it for accessibility", () => {
    for (const mood of MOODS) {
      const { unmount } = render(<HaloMascot mood={mood} />);
      expect(screen.getByRole("img")).toHaveAttribute("data-mood", mood);
      expect(screen.getByRole("img")).toHaveAttribute(
        "aria-label",
        moodSpec(mood).label,
      );
      unmount();
    }
  });

  it("draws the accessory the mood calls for, and none for idle", () => {
    const { container, rerender } = render(<HaloMascot mood="asking" />);
    expect(container.querySelector('[data-accessory="hand"]')).not.toBeNull();
    rerender(<HaloMascot mood="idle" />);
    expect(container.querySelector("[data-accessory]")).toBeNull();
  });

  it("colours the halo ring by mood", () => {
    const { container } = render(<HaloMascot mood="guarding" />);
    const ring = container.querySelector('[data-layer="ring"] path');
    expect(ring?.getAttribute("stroke")?.toLowerCase()).toBe("#ff4d5e");
  });

  it("shows one mini-halo per running sub-agent, up to four", () => {
    const { container, rerender } = render(
      <HaloMascot mood="delegating" agents={2} />,
    );
    expect(
      container.querySelectorAll('[data-testid="mini-halo"]'),
    ).toHaveLength(2);
    rerender(<HaloMascot mood="delegating" agents={9} />);
    expect(
      container.querySelectorAll('[data-testid="mini-halo"]'),
    ).toHaveLength(4);
    rerender(<HaloMascot mood="delegating" agents={0} />);
    expect(
      container.querySelectorAll('[data-testid="mini-halo"]'),
    ).toHaveLength(0);
  });

  it("only draws a progress ring in the focused mood", () => {
    const focused = render(<HaloMascot mood="focused" progress={0.5} />);
    expect(
      focused.container.querySelector('[data-layer="progress"]'),
    ).not.toBeNull();
    focused.unmount();
    const idle = render(<HaloMascot mood="idle" progress={0.5} />);
    expect(idle.container.querySelector('[data-layer="progress"]')).toBeNull();
  });
});

describe("the eyes follow the cursor", () => {
  it("looks where the gaze points, clamped to the unit square", () => {
    const { container, rerender } = render(
      <HaloMascot mood="idle" gaze={{ x: 0.5, y: -0.5 }} />,
    );
    const eyes = () => container.querySelector('[data-layer="eyes"]');
    expect(eyes()).toHaveAttribute("data-gaze-x", "0.5");
    expect(eyes()).toHaveAttribute("data-gaze-y", "-0.5");
    rerender(<HaloMascot mood="idle" gaze={{ x: 9, y: -9 }} />);
    expect(eyes()).toHaveAttribute("data-gaze-x", "1");
    expect(eyes()).toHaveAttribute("data-gaze-y", "-1");
  });

  it("looks straight ahead when there is no gaze", () => {
    const { container } = render(<HaloMascot mood="idle" />);
    const eyes = container.querySelector('[data-layer="eyes"]');
    expect(eyes).toHaveAttribute("data-gaze-x", "0");
  });
});

describe("the animation timers", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("marks busy moods as animating and idle or asleep as still", () => {
    for (const mood of ["thinking", "focused", "delegating", "careful"] as const) {
      const { container, unmount } = render(<HaloMascot mood={mood} />);
      expect(screen.getByRole("img")).toHaveAttribute("data-busy", "true");
      unmount();
      expect(container.querySelector("svg")).toBeNull();
    }
    for (const mood of ["idle", "asleep"] as const) {
      const { unmount } = render(<HaloMascot mood={mood} />);
      expect(screen.getByRole("img")).toHaveAttribute("data-busy", "false");
      unmount();
    }
  });

  it("holds perfectly still when idle or asleep", () => {
    for (const mood of ["idle", "asleep"] as const) {
      const { container, unmount } = render(<HaloMascot mood={mood} />);
      const before = bodyPath(container);
      act(() => {
        vi.advanceTimersByTime(1000);
      });
      expect(bodyPath(container)).toBe(before);
      unmount();
    }
  });

  it("stops the timer when it unmounts", () => {
    const { unmount } = render(<HaloMascot mood="thinking" />);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
