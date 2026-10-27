// Draws Halo's layers as clean vector paths. Nothing here is random: the same
// spec always gives the same shapes, and all motion is done by the mascot.
//
// The look is flat on purpose: one squircle body, two small eyes, at most a tiny
// mouth, and a small round badge in the corner. No outline, no highlight.
import type { Accessory, Eyes, MoodSpec, Mouth } from "./spec";

export interface Shape {
  d: string;
  stroke: string;
  strokeWidth: number;
  fill?: string;
  opacity?: number;
}

export interface Layers {
  shadow: Shape[];
  body: Shape[];
  cheeks: Shape[];
  eyes: Shape[];
  mouth: Shape[];
  ring: Shape[];
  /** The glyph inside the badge, or the free-floating marker (sparkles, sweat). */
  accessory: Shape[];
}

/** The badge sits on the top-left corner of the body. */
export const BADGE = { cx: 20, cy: 36, r: 9 };
export const BADGE_FILL = "#0b0c0f";
export const RING = { cx: 50, cy: 22, rx: 20, ry: 5.5 };

const INK = "#0b0c0f";
const LIGHT = "#e9eaee";
const BLUSH = "#ff8aa0";
const EYE_L = { x: 38, y: 60 };
const EYE_R = { x: 62, y: 60 };
const NONE = "none";

// A 4:3 squircle: wide and low, like a soft pillow.
const BODY_D =
  "M 36 34 H 64 C 78 34 86 42 86 56 V 64 C 86 78 78 86 64 86 H 36 C 22 86 14 78 14 64 V 56 C 14 42 22 34 36 34 Z";

const ellipseD = (cx: number, cy: number, rx: number, ry: number) =>
  `M ${cx - rx} ${cy} a ${rx} ${ry} 0 1 0 ${2 * rx} 0 a ${rx} ${ry} 0 1 0 ${-2 * rx} 0 Z`;
const circleD = (cx: number, cy: number, r: number) => ellipseD(cx, cy, r, r);
const lineD = (points: [number, number][]) =>
  points.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x} ${y}`).join(" ");
const starD = (x: number, y: number, r: number) =>
  `M ${x} ${y - r} Q ${x} ${y} ${x + r} ${y} Q ${x} ${y} ${x} ${y + r} Q ${x} ${y} ${x - r} ${y} Q ${x} ${y} ${x} ${y - r} Z`;

const ink = (d: string, width = 2.4): Shape => ({
  d,
  stroke: INK,
  strokeWidth: width,
});
const solidInk = (d: string): Shape => ({
  d,
  stroke: NONE,
  strokeWidth: 0,
  fill: INK,
});
const glyph = (d: string, width = 1.8): Shape => ({
  d,
  stroke: LIGHT,
  strokeWidth: width,
});
const glyphDot = (cx: number, cy: number, r: number): Shape => ({
  d: circleD(cx, cy, r),
  stroke: NONE,
  strokeWidth: 0,
  fill: LIGHT,
});

function spiral(cx: number, cy: number): string {
  const points: [number, number][] = [];
  for (let t = 0; t <= 3 * Math.PI; t += 0.4) {
    const r = 0.6 + t * 0.55;
    points.push([cx + r * Math.cos(t), cy + r * Math.sin(t)]);
  }
  return lineD(points);
}

function drawEyes(kind: Eyes): Shape[] {
  const both = (draw: (x: number, y: number) => Shape[]) => [
    ...draw(EYE_L.x, EYE_L.y),
    ...draw(EYE_R.x, EYE_R.y),
  ];
  switch (kind) {
    case "open":
      return both((x, y) => [solidInk(ellipseD(x, y, 3.4, 5.2))]);
    case "wide":
      return both((x, y) => [solidInk(ellipseD(x, y, 4.2, 6.4))]);
    case "upleft":
      // Looking up and to the left.
      return both((x, y) => [solidInk(ellipseD(x - 3, y - 3, 3.4, 5.2))]);
    case "squint":
      return both((x, y) => [
        ink(`M ${x - 5} ${y + 1} Q ${x} ${y - 3} ${x + 5} ${y + 1}`, 3),
      ]);
    case "closed":
      return both((x, y) => [
        ink(`M ${x - 5} ${y} Q ${x} ${y + 4} ${x + 5} ${y}`, 2.6),
      ]);
    case "happy":
      return both((x, y) => [
        ink(`M ${x - 5} ${y + 2} Q ${x} ${y - 5} ${x + 5} ${y + 2}`, 2.8),
      ]);
    case "spiral":
      return both((x, y) => [ink(spiral(x, y), 1.6)]);
  }
}

const cheeks = (): Shape[] =>
  [26, 74].map((x) => ({
    d: ellipseD(x, 71, 4, 2.6),
    stroke: NONE,
    strokeWidth: 0,
    fill: INK,
    opacity: 0.16, // a soft darker patch reads as a blush on any body colour
  }));

function drawMouth(kind: Mouth): Shape[] {
  switch (kind) {
    case "smile":
      return [ink("M 44 74 Q 50 78 56 74", 2)];
    case "grin":
      return [solidInk("M 43 72 Q 50 81 57 72 Z")];
    case "smirk":
      return [ink("M 44 75 Q 50 79 57 72", 2)];
    case "o":
      return [solidInk(ellipseD(50, 75, 3, 3.6))];
    case "flat":
      return [ink("M 45 75 L 55 75", 2)];
    case "frown":
      return [ink("M 44 77 Q 50 72 56 77", 2)];
    case "tongue":
      return [
        ink("M 44 74 Q 50 78 56 74", 2),
        {
          d: ellipseD(50, 79, 2.8, 2.8),
          stroke: NONE,
          strokeWidth: 0,
          fill: BLUSH,
        },
      ];
    case "none":
      return [];
  }
}

const { cx: BX, cy: BY } = BADGE;

/** What goes in the badge, or floats beside the body for the two that are not badges. */
function drawAccessory(kind: Accessory | null): Shape[] {
  switch (kind) {
    case null:
      return [];
    case "zzz":
      return [
        glyph(
          lineD([
            [BX - 4, BY - 4],
            [BX + 4, BY - 4],
            [BX - 4, BY + 4],
            [BX + 4, BY + 4],
          ]),
        ),
      ];
    case "thoughts":
      return [
        glyphDot(BX - 5, BY, 1.5),
        glyphDot(BX, BY, 1.5),
        glyphDot(BX + 5, BY, 1.5),
      ];
    case "magnifier":
      return [
        glyph(circleD(BX - 1, BY - 1, 3.8), 1.6),
        glyph(
          lineD([
            [BX + 2, BY + 2],
            [BX + 5, BY + 5],
          ]),
          2,
        ),
      ];
    case "pencil":
      return [
        glyph(
          lineD([
            [BX - 1, BY + 1],
            [BX + 4, BY - 4],
          ]),
          3.2,
        ),
        // The sharpened tip, filled, so it reads as a pencil and not a slash.
        {
          d: `M ${BX - 5} ${BY + 5} L ${BX - 4} ${BY + 0.5} L ${BX - 0.5} ${BY + 4} Z`,
          stroke: NONE,
          strokeWidth: 0,
          fill: LIGHT,
        },
      ];
    case "hand":
      // A question mark: Halo is asking.
      return [
        glyph(
          `M ${BX - 3} ${BY - 3} Q ${BX - 3} ${BY - 6} ${BX} ${BY - 6} Q ${BX + 3} ${BY - 6} ${BX + 3} ${BY - 3} Q ${BX + 3} ${BY - 1} ${BX} ${BY} V ${BY + 2}`,
          1.8,
        ),
        glyphDot(BX, BY + 5, 1.1),
      ];
    case "shield":
      return [
        glyph(
          `M ${BX} ${BY - 6} L ${BX + 5} ${BY - 4} V ${BY + 1} Q ${BX + 5} ${BY + 5} ${BX} ${BY + 7} Q ${BX - 5} ${BY + 5} ${BX - 5} ${BY + 1} V ${BY - 4} Z`,
          1.6,
        ),
      ];
    case "sparkles":
      return [
        {
          d: starD(86, 36, 7),
          stroke: NONE,
          strokeWidth: 0,
          fill: "#ffe27a",
        },
        {
          d: starD(12, 50, 5),
          stroke: NONE,
          strokeWidth: 0,
          fill: "#ffe27a",
        },
      ];
    case "sweat":
      return [
        {
          d: "M 84 38 Q 90 46 84 51 Q 78 46 84 38 Z",
          stroke: NONE,
          strokeWidth: 0,
          fill: "#8ad0ff",
        },
      ];
  }
}

export function drawLayers(spec: MoodSpec): Layers {
  return {
    // A soft pool of light under the body. A dark shadow vanishes on a near-black
    // window, so the ground is a faint lighter ellipse instead.
    shadow: [
      {
        d: ellipseD(50, 90, 30, 3.4),
        stroke: NONE,
        strokeWidth: 0,
        fill: "#ffffff",
        opacity: 0.1,
      },
    ],
    body: [{ d: BODY_D, stroke: NONE, strokeWidth: 0, fill: spec.body }],
    cheeks: spec.cheeks ? cheeks() : [],
    eyes: drawEyes(spec.eyes),
    mouth: drawMouth(spec.mouth),
    ring: [
      {
        d: ellipseD(RING.cx, RING.cy, RING.rx, RING.ry),
        stroke: spec.ring,
        strokeWidth: 2.4,
      },
    ],
    accessory: drawAccessory(spec.accessory),
  };
}
