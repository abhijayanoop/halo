// Draws Halo's layers as sketchy paths with Rough.js. A different `seed` gives
// a different wobble of the same shape, which is what makes the outline "boil".
//
// The bean's body is light with dark ink, but accessories mostly sit on the dark
// glass bar, so they are outlined in a light tone and filled with colour.
import rough from "roughjs";
import type { Options, PathInfo } from "roughjs/bin/core";
import type { Accessory, Eyes, MoodSpec, Mouth } from "./spec";

const generator = rough.generator();

const INK = "#23232e";
const BODY = "#f6f1e7";
const LIGHT = "#e8ecf4"; // outline for things drawn on the dark bar
const EYE_L = { x: 40, y: 54 };
const EYE_R = { x: 62, y: 54 };

export interface Layers {
  body: PathInfo[];
  eyes: PathInfo[];
  brow: PathInfo[];
  mouth: PathInfo[];
  ring: PathInfo[];
  accessory: PathInfo[];
}

const line = (seed: number, extra: Options = {}): Options => ({
  seed,
  roughness: 1.3,
  strokeWidth: 2.2,
  stroke: INK,
  ...extra,
});
const solid = (seed: number, fill: string, extra: Options = {}): Options =>
  line(seed, { fill, fillStyle: "solid", ...extra });
// Accessory styles: light outline, coloured fill.
const outline = (seed: number, extra: Options = {}): Options =>
  line(seed, { stroke: LIGHT, strokeWidth: 2, ...extra });
const filled = (seed: number, fill: string, extra: Options = {}): Options =>
  outline(seed, { fill, fillStyle: "solid", ...extra });

const paths = (...drawables: ReturnType<typeof generator.path>[]): PathInfo[] =>
  drawables.flatMap((d) => generator.toPaths(d));

const BEAN =
  "M 22 58 C 20 34, 40 26, 54 28 C 74 30, 82 46, 78 64 C 74 82, 54 88, 40 84 C 28 80, 24 72, 22 58 Z";

function spiral(cx: number, cy: number): [number, number][] {
  const points: [number, number][] = [];
  for (let t = 0; t <= 3 * Math.PI; t += 0.5) {
    const r = 1 + t * 0.9;
    points.push([cx + r * Math.cos(t), cy + r * Math.sin(t)]);
  }
  return points;
}

function drawEyes(kind: Eyes, seed: number): PathInfo[] {
  const both = (
    draw: (x: number, y: number) => ReturnType<typeof generator.path>,
  ) => paths(draw(EYE_L.x, EYE_L.y), draw(EYE_R.x, EYE_R.y));
  switch (kind) {
    case "open":
      return both((x, y) => generator.ellipse(x, y, 7, 10, solid(seed, INK)));
    case "wide":
      return both((x, y) => generator.ellipse(x, y, 10, 14, solid(seed, INK)));
    case "upleft":
      // Looking up and to the left: pupils pushed well off-centre.
      return both((x, y) =>
        generator.ellipse(x - 4, y - 5, 7, 10, solid(seed, INK)),
      );
    case "squint":
      return both((x, y) =>
        generator.path(
          `M ${x - 5} ${y} L ${x + 5} ${y}`,
          line(seed, { strokeWidth: 3 }),
        ),
      );
    case "closed":
      return both((x, y) =>
        generator.path(
          `M ${x - 5} ${y} Q ${x} ${y + 4} ${x + 5} ${y}`,
          line(seed),
        ),
      );
    case "happy":
      return both((x, y) =>
        generator.path(
          `M ${x - 5} ${y + 2} Q ${x} ${y - 6} ${x + 5} ${y + 2}`,
          line(seed, { strokeWidth: 2.8 }),
        ),
      );
    case "spiral":
      return both((x, y) =>
        generator.linearPath(spiral(x, y), line(seed, { strokeWidth: 1.6 })),
      );
  }
}

function drawMouth(kind: Mouth, seed: number): PathInfo[] {
  switch (kind) {
    case "smile":
      return paths(generator.path("M 44 70 Q 51 77 58 70", line(seed)));
    case "grin":
      return paths(generator.path("M 42 69 Q 51 84 60 69 Z", solid(seed, INK)));
    case "o":
      return paths(generator.ellipse(51, 73, 6, 7, solid(seed, INK)));
    case "flat":
      return paths(
        generator.linearPath(
          [
            [45, 72],
            [57, 72],
          ],
          line(seed),
        ),
      );
    case "frown":
      return paths(generator.path("M 44 76 Q 51 68 58 76", line(seed)));
    case "tongue":
      return paths(
        generator.ellipse(
          51,
          80,
          9,
          9,
          solid(seed, "#ff7f98", { strokeWidth: 1.4 }),
        ),
        generator.path("M 43 70 Q 51 77 59 70", line(seed)),
      );
    case "none":
      return [];
  }
}

const star = (x: number, y: number, r: number) =>
  `M ${x} ${y - r} L ${x + r / 4} ${y - r / 4} L ${x + r} ${y} L ${x + r / 4} ${y + r / 4} L ${x} ${y + r} L ${x - r / 4} ${y + r / 4} L ${x - r} ${y} L ${x - r / 4} ${y - r / 4} Z`;

// Accessories keep clear of the face (x 30-72, y 44-80) so the mood stays readable.
function drawAccessory(kind: Accessory | null, seed: number): PathInfo[] {
  switch (kind) {
    case null:
      return [];
    case "zzz":
      return paths(
        generator.linearPath(
          [
            [74, 26],
            [84, 26],
            [74, 36],
            [84, 36],
          ],
          outline(seed, { strokeWidth: 2.6 }),
        ),
        generator.linearPath(
          [
            [88, 10],
            [95, 10],
            [88, 17],
            [95, 17],
          ],
          outline(seed, { strokeWidth: 2.2 }),
        ),
      );
    case "thoughts":
      return paths(
        generator.circle(80, 42, 5, filled(seed, "#c9d4ff")),
        generator.circle(86, 31, 8, filled(seed, "#c9d4ff")),
        generator.circle(93, 17, 13, filled(seed, "#e8eeff")),
      );
    case "magnifier":
      return paths(
        generator.circle(
          88,
          64,
          20,
          filled(seed, "#9fd8ff55", { strokeWidth: 2.6 }),
        ),
        generator.linearPath(
          [
            [95, 73],
            [104, 85],
          ],
          outline(seed, { strokeWidth: 3.6 }),
        ),
      );
    case "pencil":
      return paths(
        generator.rectangle(2, 60, 16, 22, filled(seed, "#fffdf2", { stroke: LIGHT })),
        generator.polygon(
          [
            [76, 82],
            [86, 64],
            [98, 70],
            [88, 88],
          ],
          filled(seed, "#ffd45e", { strokeWidth: 2.2 }),
        ),
        generator.polygon(
          [
            [76, 82],
            [88, 88],
            [72, 94],
          ],
          filled(seed, "#f4a38c"),
        ),
      );
    case "hand":
      return paths(
        generator.path(
          "M 76 76 Q 92 72 93 50",
          outline(seed, { strokeWidth: 3.4 }),
        ),
        generator.circle(93, 42, 15, filled(seed, BODY)),
        generator.linearPath(
          [
            [88, 36],
            [87, 28],
          ],
          outline(seed, { strokeWidth: 2.4 }),
        ),
        generator.linearPath(
          [
            [93, 34],
            [93, 25],
          ],
          outline(seed, { strokeWidth: 2.4 }),
        ),
        generator.linearPath(
          [
            [98, 36],
            [99, 28],
          ],
          outline(seed, { strokeWidth: 2.4 }),
        ),
      );
    case "shield":
      return paths(
        generator.path(
          "M 82 42 L 102 42 L 102 60 Q 102 73 92 80 Q 82 73 82 60 Z",
          filled(seed, "#ff7a88", { strokeWidth: 2.4 }),
        ),
      );
    case "sparkles":
      return paths(
        generator.path(
          star(10, 28, 10),
          filled(seed, "#ffe27a", { strokeWidth: 1.6 }),
        ),
        generator.path(
          star(92, 36, 9),
          filled(seed, "#ffe27a", { strokeWidth: 1.6 }),
        ),
        generator.path(
          star(84, 8, 7),
          filled(seed, "#ffe27a", { strokeWidth: 1.6 }),
        ),
      );
    case "sweat":
      return paths(
        generator.path(
          "M 86 26 Q 95 38 86 46 Q 77 38 86 26 Z",
          filled(seed, "#8ad0ff", { strokeWidth: 1.8 }),
        ),
      );
  }
}

export function drawLayers(spec: MoodSpec, seed: number): Layers {
  return {
    // One stroke pass on the body: Rough.js's double stroke leaves a visible
    // spike where the outline starts and ends.
    body: paths(
      generator.path(
        BEAN,
        solid(seed, BODY, { strokeWidth: 2.6, disableMultiStroke: true }),
      ),
    ),
    eyes: drawEyes(spec.eyes, seed),
    brow: spec.eyebrow
      ? paths(generator.path("M 56 44 L 68 40", line(seed, { strokeWidth: 2 })))
      : [],
    mouth: drawMouth(spec.mouth, seed),
    ring: paths(
      generator.ellipse(
        50,
        14,
        42,
        12,
        line(seed, { stroke: spec.ring, strokeWidth: 3.2 }),
      ),
    ),
    accessory: drawAccessory(spec.accessory, seed),
  };
}
