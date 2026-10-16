// Draws Halo's layers as clean vector paths. Nothing here is random: the same
// spec always gives the same shapes, and all motion is done by the mascot.
//
// The body is a light squircle with dark ink, but accessories mostly sit on the
// dark glass bar, so they are outlined in a light tone and filled with colour.
import type { Accessory, Brow, Eyes, MoodSpec, Mouth } from "./spec";

export interface Shape {
  d: string;
  stroke: string;
  strokeWidth: number;
  fill?: string;
  opacity?: number;
}

export interface Layers {
  body: Shape[];
  eyes: Shape[];
  brow: Shape[];
  mouth: Shape[];
  ring: Shape[];
  accessory: Shape[];
}

export const BODY_GRADIENT = { top: "#fffdf8", bottom: "#ece4d3" };
const INK = "#23232e";
const LIGHT = "#e8ecf4"; // outline for things drawn on the dark bar
const BLUSH = "#ff9db0";
const EYE_L = { x: 39, y: 56 };
const EYE_R = { x: 61, y: 56 };
const NONE = "none";

const BODY_D =
  "M 24 58 C 24 38, 37 28, 50 28 C 63 28, 76 38, 76 58 C 76 78, 64 87, 50 87 C 36 87, 24 78, 24 58 Z";

// Shape helpers: every shape is one path string.
const ellipseD = (cx: number, cy: number, rx: number, ry: number) =>
  `M ${cx - rx} ${cy} a ${rx} ${ry} 0 1 0 ${2 * rx} 0 a ${rx} ${ry} 0 1 0 ${-2 * rx} 0 Z`;
const circleD = (cx: number, cy: number, r: number) => ellipseD(cx, cy, r, r);
const polyD = (points: [number, number][]) =>
  `${points.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x} ${y}`).join(" ")} Z`;
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
  stroke: INK,
  strokeWidth: 1,
  fill: INK,
});
const shine = (cx: number, cy: number, r: number): Shape => ({
  d: circleD(cx, cy, r),
  stroke: NONE,
  strokeWidth: 0,
  fill: "#ffffff",
});
const outline = (d: string, width = 2): Shape => ({
  d,
  stroke: LIGHT,
  strokeWidth: width,
});
const filled = (d: string, fill: string, width = 2): Shape => ({
  d,
  stroke: LIGHT,
  strokeWidth: width,
  fill,
});

function spiral(cx: number, cy: number): string {
  const points: [number, number][] = [];
  for (let t = 0; t <= 3 * Math.PI; t += 0.4) {
    const r = 0.8 + t * 0.95;
    points.push([cx + r * Math.cos(t), cy + r * Math.sin(t)]);
  }
  return lineD(points);
}

/** A glossy eye: a dark oval with a bright highlight, which is what makes it look alive. */
function glossyEye(
  x: number,
  y: number,
  rx: number,
  ry: number,
  dx = 0,
  dy = 0,
): Shape[] {
  const cx = x + dx;
  const cy = y + dy;
  return [
    solidInk(ellipseD(cx, cy, rx, ry)),
    shine(cx - rx * 0.32, cy - ry * 0.4, rx * 0.34),
    shine(cx + rx * 0.35, cy + ry * 0.38, rx * 0.16),
  ];
}

function drawEyes(kind: Eyes): Shape[] {
  const both = (draw: (x: number, y: number) => Shape[]) => [
    ...draw(EYE_L.x, EYE_L.y),
    ...draw(EYE_R.x, EYE_R.y),
  ];
  switch (kind) {
    case "open":
      return both((x, y) => glossyEye(x, y, 5.6, 8));
    case "wide":
      return both((x, y) => glossyEye(x, y, 6.8, 10));
    case "upleft":
      // Looking up and to the left: pupils pushed well off-centre.
      return both((x, y) => glossyEye(x, y, 5.6, 8, -3.5, -4));
    case "squint":
      return both((x, y) => [
        ink(`M ${x - 6} ${y + 1} Q ${x} ${y - 4} ${x + 6} ${y + 1}`, 3.6),
        ink(`M ${x - 5} ${y + 3} Q ${x} ${y + 5} ${x + 5} ${y + 3}`, 1.8),
      ]);
    case "closed":
      return both((x, y) => [
        ink(`M ${x - 6} ${y} Q ${x} ${y + 5} ${x + 6} ${y}`, 2.6),
      ]);
    case "happy":
      return both((x, y) => [
        ink(`M ${x - 6} ${y + 3} Q ${x} ${y - 7} ${x + 6} ${y + 3}`, 3.2),
      ]);
    case "spiral":
      return both((x, y) => [ink(spiral(x, y), 1.8)]);
  }
}

function drawBrows(kind: Brow): Shape[] {
  switch (kind) {
    case "none":
      return [];
    case "raised":
      return [
        ink("M 32 42 Q 39 37 46 42", 2.2),
        ink("M 54 42 Q 61 37 68 42", 2.2),
      ];
    case "furrow":
      return [ink("M 32 41 L 46 46", 2.6), ink("M 68 41 L 54 46", 2.6)];
    case "worry":
      return [ink("M 32 46 L 46 41", 2.4), ink("M 68 46 L 54 41", 2.4)];
  }
}

const cheeks = (): Shape[] => [
  {
    d: ellipseD(31, 67, 4.2, 2.6),
    stroke: NONE,
    strokeWidth: 0,
    fill: BLUSH,
    opacity: 0.45,
  },
  {
    d: ellipseD(69, 67, 4.2, 2.6),
    stroke: NONE,
    strokeWidth: 0,
    fill: BLUSH,
    opacity: 0.45,
  },
];

function drawMouth(kind: Mouth): Shape[] {
  switch (kind) {
    case "smile":
      return [ink("M 43 69 Q 50 76 57 69"), ...cheeks()];
    case "grin":
      return [solidInk("M 41 67 Q 50 83 59 67 Z"), ...cheeks()];
    case "smirk":
      return [ink("M 43 70 Q 51 77 59 67"), ...cheeks()];
    case "o":
      return [solidInk(ellipseD(50, 72, 4.4, 5.6))];
    case "flat":
      return [ink("M 44 72 L 56 72")];
    case "frown":
      return [ink("M 43 75 Q 50 68 57 75")];
    case "tongue":
      return [
        {
          d: ellipseD(50, 76, 5, 5.6),
          stroke: INK,
          strokeWidth: 1.4,
          fill: "#ff7f98",
        },
        ink("M 42 69 Q 50 76 58 69"),
        ...cheeks(),
      ];
    case "none":
      return [];
  }
}

// Accessories keep clear of the face (x 30-72, y 44-80) so the mood stays readable.
function drawAccessory(kind: Accessory | null): Shape[] {
  switch (kind) {
    case null:
      return [];
    case "zzz":
      return [
        outline(
          lineD([
            [74, 26],
            [84, 26],
            [74, 36],
            [84, 36],
          ]),
          2.6,
        ),
        outline(
          lineD([
            [88, 10],
            [95, 10],
            [88, 17],
            [95, 17],
          ]),
          2.2,
        ),
      ];
    case "thoughts":
      return [
        filled(circleD(80, 42, 4), "#c9d4ff"),
        filled(circleD(86, 31, 6.5), "#c9d4ff"),
        filled(circleD(93, 17, 11), "#e8eeff"),
      ];
    case "magnifier":
      return [
        filled(circleD(88, 64, 14), "#9fd8ff66", 2.6),
        outline(
          lineD([
            [98, 74],
            [105, 85],
          ]),
          3.8,
        ),
      ];
    case "pencil":
      return [
        filled(
          polyD([
            [76, 82],
            [86, 64],
            [98, 70],
            [88, 88],
          ]),
          "#ffd45e",
          2.2,
        ),
        filled(
          polyD([
            [76, 82],
            [88, 88],
            [72, 94],
          ]),
          "#f4a38c",
        ),
      ];
    case "hand":
      return [
        outline("M 76 76 Q 92 72 93 50", 3.6),
        filled(circleD(93, 42, 12), "#fffdf8"),
        outline(
          lineD([
            [88, 36],
            [87, 28],
          ]),
          2.4,
        ),
        outline(
          lineD([
            [93, 34],
            [93, 25],
          ]),
          2.4,
        ),
        outline(
          lineD([
            [98, 36],
            [99, 28],
          ]),
          2.4,
        ),
      ];
    case "shield":
      return [
        filled(
          "M 82 42 L 102 42 L 102 60 Q 102 73 92 80 Q 82 73 82 60 Z",
          "#ff7a88",
          2.4,
        ),
      ];
    case "sparkles":
      return [
        filled(starD(10, 28, 9), "#ffe27a", 1.4),
        filled(starD(92, 36, 8), "#ffe27a", 1.4),
        filled(starD(84, 8, 6), "#ffe27a", 1.4),
      ];
    case "sweat":
      return [filled("M 86 26 Q 95 38 86 46 Q 77 38 86 26 Z", "#8ad0ff", 1.8)];
  }
}

export function drawLayers(spec: MoodSpec): Layers {
  return {
    body: [
      {
        d: BODY_D,
        stroke: "#cfc6b3",
        strokeWidth: 1.4,
        fill: "url(#halo-body)",
      },
      // A soft highlight on the top left, which gives the body its volume.
      {
        d: "M 32 46 Q 33 36 44 33",
        stroke: "#ffffff",
        strokeWidth: 3,
        opacity: 0.7,
      },
    ],
    eyes: drawEyes(spec.eyes),
    brow: drawBrows(spec.brow),
    mouth: drawMouth(spec.mouth),
    ring: [
      {
        d: ellipseD(50, 14, 22, 6.5),
        stroke: spec.ring,
        strokeWidth: 3.4,
      },
    ],
    accessory: drawAccessory(spec.accessory),
  };
}
