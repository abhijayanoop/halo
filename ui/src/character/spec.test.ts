import { describe, expect, it } from "vitest";
import { MOODS } from "../state/reducer";
import { moodSpec } from "./spec";

describe("moodSpec", () => {
  it("defines a look for every one of the 13 moods", () => {
    expect(MOODS).toHaveLength(13);
    for (const mood of MOODS) {
      const spec = moodSpec(mood);
      expect(spec.ring).toMatch(/^#[0-9a-f]{6}$/i);
      expect(spec.label.length).toBeGreaterThan(0);
    }
  });

  it("uses the agreed ring colours", () => {
    const ring = (m: (typeof MOODS)[number]) => moodSpec(m).ring.toLowerCase();
    // grey idle, blue thinking, violet working, amber asking, red guarding, green success
    expect(ring("idle")).toBe("#9aa3b2");
    expect(ring("thinking")).toBe("#5b8cff");
    expect(ring("focused")).toBe("#9b6bff");
    expect(ring("asking")).toBe("#ffb020");
    expect(ring("guarding")).toBe("#ff4d5e");
    expect(ring("delighted")).toBe("#3ddc97");
  });

  it("gives every working mood the violet ring", () => {
    for (const mood of [
      "focused",
      "delegating",
      "careful",
      "remembering",
    ] as const) {
      expect(moodSpec(mood).ring.toLowerCase()).toBe("#9b6bff");
    }
  });

  it("boils the outline only while Halo is busy, and holds still otherwise", () => {
    const busy = MOODS.filter((m) => moodSpec(m).busy);
    expect(busy.sort()).toEqual([
      "careful",
      "delegating",
      "focused",
      "remembering",
      "thinking",
    ]);
    expect(moodSpec("idle").busy).toBe(false);
    expect(moodSpec("asleep").busy).toBe(false);
  });

  it("gives each mood at most one accessory, matching the mood table", () => {
    expect(moodSpec("asleep").accessory).toBe("zzz");
    expect(moodSpec("thinking").accessory).toBe("thoughts");
    expect(moodSpec("careful").accessory).toBe("magnifier");
    expect(moodSpec("remembering").accessory).toBe("pencil");
    expect(moodSpec("asking").accessory).toBe("hand");
    expect(moodSpec("guarding").accessory).toBe("shield");
    expect(moodSpec("delighted").accessory).toBe("sparkles");
    expect(moodSpec("confused").accessory).toBe("sweat");
    expect(moodSpec("idle").accessory).toBeNull();
  });

  it("matches the face to the mood", () => {
    expect(moodSpec("asleep").eyes).toBe("closed");
    expect(moodSpec("delighted").eyes).toBe("happy");
    expect(moodSpec("confused").eyes).toBe("spiral");
    expect(moodSpec("focused").eyes).toBe("squint");
    expect(moodSpec("focused").mouth).toBe("tongue");
    expect(moodSpec("listening").mouth).toBe("o");
    expect(moodSpec("guarding").mouth).toBe("frown");
  });

  it("only the focused mood turns the ring into a progress ring", () => {
    expect(MOODS.filter((m) => moodSpec(m).ringStyle === "progress")).toEqual([
      "focused",
    ]);
  });
});
