// What each mood looks like. Pure data: the mascot only draws what this says,
// and the mood itself always comes from the Python core.
import type { Mood } from "../state/reducer";

export type Eyes =
  "open" | "closed" | "wide" | "squint" | "happy" | "spiral" | "upleft";
export type Mouth =
  "smile" | "grin" | "o" | "flat" | "frown" | "tongue" | "none";
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
  accessory: Accessory | null;
  eyebrow: boolean;
  motion: Motion;
  busy: boolean; // redraw the outline ~8 times a second
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
  accessory: null,
  eyebrow: false,
  motion: "none",
  busy: false,
};

const SPECS: Record<Mood, MoodSpec> = {
  asleep: {
    ...base,
    label: "Asleep",
    ring: "#5b6270",
    eyes: "closed",
    mouth: "flat",
    accessory: "zzz",
    motion: "slow",
  },
  waking: {
    ...base,
    label: "Waking",
    ring: "#c9d4ff",
    eyes: "wide",
    mouth: "smile",
    eyebrow: true,
    motion: "squash",
  },
  idle: { ...base },
  listening: {
    ...base,
    label: "Listening",
    ring: "#4cc9f0",
    eyes: "wide",
    mouth: "o",
    motion: "pulse",
  },
  thinking: {
    ...base,
    label: "Thinking",
    ring: BLUE,
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
    eyes: "squint",
    mouth: "tongue",
    busy: true,
  },
  delegating: {
    ...base,
    label: "Delegating",
    ring: VIOLET,
    mouth: "smile",
    busy: true,
  },
  careful: {
    ...base,
    label: "Careful",
    ring: VIOLET,
    eyes: "open",
    mouth: "flat",
    accessory: "magnifier",
    eyebrow: true,
    busy: true,
  },
  remembering: {
    ...base,
    label: "Remembering",
    ring: VIOLET,
    mouth: "smile",
    accessory: "pencil",
    busy: true,
  },
  asking: {
    ...base,
    label: "Asking",
    ring: AMBER,
    eyes: "wide",
    mouth: "smile",
    accessory: "hand",
    motion: "pulse",
  },
  guarding: {
    ...base,
    label: "Guarding",
    ring: RED,
    eyes: "squint",
    mouth: "frown",
    accessory: "shield",
  },
  delighted: {
    ...base,
    label: "Delighted",
    ring: GREEN,
    eyes: "happy",
    mouth: "grin",
    accessory: "sparkles",
    motion: "bounce",
  },
  confused: {
    ...base,
    label: "Confused",
    ring: "#f08a5d",
    eyes: "spiral",
    mouth: "frown",
    accessory: "sweat",
  },
};

export function moodSpec(mood: Mood): MoodSpec {
  return SPECS[mood];
}
