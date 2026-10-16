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

describe("moodSpec, the flat minimal mascot", () => {
  it("colours the body by mood: near-white idle, otherwise the mood colour", () => {
    expect(moodSpec("idle").body.toLowerCase()).toBe("#e9eaee");
    for (const mood of MOODS) {
      const { body, ring } = moodSpec(mood);
      expect(body).toMatch(/^#[0-9a-f]{6}$/i);
      if (mood !== "idle" && mood !== "asleep") expect(body).toBe(ring);
    }
  });

  it("asleep is a dim grey body, not a bright one", () => {
    expect(moodSpec("asleep").body.toLowerCase()).toBe("#6b7080");
  });

  it("tells every mood apart by eyes, mouth, badge and colour together", () => {
    const looks = MOODS.map((m) => {
      const s = moodSpec(m);
      return `${s.eyes}|${s.mouth}|${s.accessory}|${s.body}`;
    });
    expect(new Set(looks).size).toBe(MOODS.length);
  });

  it("has no mouth at rest: the eyes carry the face", () => {
    expect(moodSpec("idle").mouth).toBe("none");
  });

  it("shows cheeks only when delighted or confused", () => {
    expect(MOODS.filter((m) => moodSpec(m).cheeks)).toEqual([
      "delighted",
      "confused",
    ]);
  });

  it("puts a badge in the corner for these accessories, and draws the rest free", () => {
    const badged = MOODS.filter((m) => moodSpec(m).badge).map(
      (m) => moodSpec(m).accessory,
    );
    expect(badged.sort()).toEqual(
      ["hand", "magnifier", "pencil", "shield", "thoughts", "zzz"].sort(),
    );
    expect(moodSpec("delighted").badge).toBe(false);
    expect(moodSpec("confused").badge).toBe(false);
  });
});
