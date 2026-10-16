// What each mood looks like. Pure data: the mascot only draws what this says,
// and the mood itself always comes from the Python core.
import type { Mood } from "../state/reducer";

export type Eyes =
  "open" | "closed" | "wide" | "squint" | "happy" | "spiral" | "upleft";
export type Mouth =
  "smile" | "grin" | "o" | "flat" | "frown" | "tongue" | "smirk" | "none";
export type Brow = "none" | "raised" | "furrow" | "worry";
export type Accessory =
  | "zzz"
  | "thoughts"
  | "magnifier"
  | "pencil"
  | "hand"
  | "shield"
  | "sparkles"
  | "sweat";
export type RingStyle = "plain" | "progress";
export type Motion = "none" | "spin" | "pulse" | "bounce" | "squash" | "slow";

export interface MoodSpec {
  label: string;
  ring: string;
  ringStyle: RingStyle;
  eyes: Eyes;
  mouth: Mouth;
  brow: Brow;
  glow: number; // 0..1, how strongly the ring glows
  accessory: Accessory | null;
  motion: Motion;
  busy: boolean; // the body shows a gentle working motion
}

const GREY = "#9aa3b2";
const BLUE = "#5b8cff";
const VIOLET = "#9b6bff";
const AMBER = "#ffb020";
const RED = "#ff4d5e";
const GREEN = "#3ddc97";

const base: MoodSpec = {
  label: "Idle",
  ring: GREY,
  ringStyle: "plain",
  eyes: "open",
  mouth: "smile",
  brow: "none",
  glow: 0.25,
  accessory: null,
  motion: "none",
  busy: false,
};

// Every mood has its own eyes + mouth + brow, so the face reads on its own
// even when the accessory is too small to make out.
const SPECS: Record<Mood, MoodSpec> = {
  asleep: {
    ...base,
    label: "Asleep",
    ring: "#5b6270",
    glow: 0.1,
    eyes: "closed",
    mouth: "flat",
    accessory: "zzz",
    motion: "slow",
  },
  waking: {
    ...base,
    label: "Waking",
    ring: "#c9d4ff",
    glow: 0.5,
    eyes: "wide",
    mouth: "smile",
    brow: "raised",
    motion: "squash",
  },
  idle: { ...base },
  listening: {
    ...base,
    label: "Listening",
    ring: "#4cc9f0",
    glow: 0.6,
    eyes: "wide",
    mouth: "o",
    brow: "raised",
    motion: "pulse",
  },
  thinking: {
    ...base,
    label: "Thinking",
    ring: BLUE,
    glow: 0.6,
    eyes: "upleft",
    mouth: "flat",
    accessory: "thoughts",
    motion: "spin",
    busy: true,
  },
  focused: {
    ...base,
    label: "Focused",
    ring: VIOLET,
    ringStyle: "progress",
    glow: 0.7,
    eyes: "squint",
    mouth: "tongue",
    brow: "furrow",
    busy: true,
  },
  delegating: {
    ...base,
    label: "Delegating",
    ring: VIOLET,
    glow: 0.6,
    mouth: "smirk",
    brow: "raised",
    busy: true,
  },
  careful: {
    ...base,
    label: "Careful",
    ring: VIOLET,
    glow: 0.6,
    eyes: "open",
    mouth: "flat",
    brow: "furrow",
    accessory: "magnifier",
    busy: true,
  },
  remembering: {
    ...base,
    label: "Remembering",
    ring: VIOLET,
    glow: 0.6,
    mouth: "smile",
    brow: "raised",
    accessory: "pencil",
    busy: true,
  },
  asking: {
    ...base,
    label: "Asking",
    ring: AMBER,
    glow: 0.9,
    eyes: "wide",
    mouth: "smile",
    brow: "worry",
    accessory: "hand",
    motion: "pulse",
  },
  guarding: {
    ...base,
    label: "Guarding",
    ring: RED,
    glow: 0.9,
    eyes: "squint",
    mouth: "frown",
    brow: "furrow",
    accessory: "shield",
  },
  delighted: {
    ...base,
    label: "Delighted",
    ring: GREEN,
    glow: 0.8,
    eyes: "happy",
    mouth: "grin",
    brow: "raised",
    accessory: "sparkles",
    motion: "bounce",
  },
  confused: {
    ...base,
    label: "Confused",
    ring: "#f08a5d",
    glow: 0.4,
    eyes: "spiral",
    mouth: "frown",
    accessory: "sweat",
  },
};

export function moodSpec(mood: Mood): MoodSpec {
  return SPECS[mood];
}
