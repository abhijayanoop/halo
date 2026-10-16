// What each mood looks like. Pure data: the mascot only draws what this says,
// and the mood itself always comes from the Python core.
//
// The mascot is deliberately quiet: one flat body whose colour is the state,
// two small eyes, and at most a small badge in the corner. Colour is the main
// signal; the face only adds to it.
import type { Mood } from "../state/reducer";

export type Eyes =
  "open" | "closed" | "wide" | "squint" | "happy" | "spiral" | "upleft";
export type Mouth =
  "smile" | "grin" | "o" | "flat" | "frown" | "tongue" | "smirk" | "none";
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
  /** The thin halo above the head, and the colour of the badge edge. */
  ring: string;
  ringStyle: RingStyle;
  /** The flat body fill: near-white when idle, the mood colour otherwise. */
  body: string;
  eyes: Eyes;
  mouth: Mouth;
  cheeks: boolean;
  accessory: Accessory | null;
  /** Draw the accessory as a glyph in a round badge on the corner. */
  badge: boolean;
  motion: Motion;
  busy: boolean; // the body shows a gentle working motion
}

const GREY = "#9aa3b2";
const BLUE = "#5b8cff";
const VIOLET = "#9b6bff";
const AMBER = "#ffb020";
const RED = "#ff4d5e";
const GREEN = "#3ddc97";
const WHITE = "#e9eaee";

const base: MoodSpec = {
  label: "Idle",
  ring: GREY,
  ringStyle: "plain",
  body: WHITE,
  eyes: "open",
  mouth: "none",
  cheeks: false,
  accessory: null,
  badge: false,
  motion: "none",
  busy: false,
};

const SPECS: Record<Mood, MoodSpec> = {
  asleep: {
    ...base,
    label: "Asleep",
    ring: "#5b6270",
    body: "#6b7080",
    eyes: "closed",
    mouth: "flat",
    accessory: "zzz",
    badge: true,
    motion: "slow",
  },
  waking: {
    ...base,
    label: "Waking",
    ring: "#c9d4ff",
    body: "#c9d4ff",
    eyes: "wide",
    mouth: "smile",
    motion: "squash",
  },
  idle: { ...base },
  listening: {
    ...base,
    label: "Listening",
    ring: "#4cc9f0",
    body: "#4cc9f0",
    eyes: "wide",
    mouth: "o",
    motion: "pulse",
  },
  thinking: {
    ...base,
    label: "Thinking",
    ring: BLUE,
    body: BLUE,
    eyes: "upleft",
    mouth: "flat",
    accessory: "thoughts",
    badge: true,
    motion: "spin",
    busy: true,
  },
  focused: {
    ...base,
    label: "Focused",
    ring: VIOLET,
    ringStyle: "progress",
    body: VIOLET,
    eyes: "squint",
    mouth: "tongue",
    busy: true,
  },
  delegating: {
    ...base,
    label: "Delegating",
    ring: VIOLET,
    body: VIOLET,
    mouth: "smirk",
    busy: true,
  },
  careful: {
    ...base,
    label: "Careful",
    ring: VIOLET,
    body: VIOLET,
    mouth: "flat",
    accessory: "magnifier",
    badge: true,
    busy: true,
  },
  remembering: {
    ...base,
    label: "Remembering",
    ring: VIOLET,
    body: VIOLET,
    mouth: "smile",
    accessory: "pencil",
    badge: true,
    busy: true,
  },
  asking: {
    ...base,
    label: "Asking",
    ring: AMBER,
    body: AMBER,
    eyes: "wide",
    mouth: "smile",
    accessory: "hand",
    badge: true,
    motion: "pulse",
  },
  guarding: {
    ...base,
    label: "Guarding",
    ring: RED,
    body: RED,
    eyes: "squint",
    mouth: "frown",
    accessory: "shield",
    badge: true,
  },
  delighted: {
    ...base,
    label: "Delighted",
    ring: GREEN,
    body: GREEN,
    eyes: "happy",
    mouth: "grin",
    cheeks: true,
    accessory: "sparkles",
    motion: "bounce",
  },
  confused: {
    ...base,
    label: "Confused",
    ring: "#f08a5d",
    body: "#f08a5d",
    eyes: "spiral",
    mouth: "frown",
    cheeks: true,
    accessory: "sweat",
  },
};

export function moodSpec(mood: Mood): MoodSpec {
  return SPECS[mood];
}
