// Draws Halo's layers as sketchy paths with Rough.js. A different `seed` gives
// a different wobble of the same shape, which is what makes the outline "boil".
import rough from "roughjs";
import type { Options, PathInfo } from "roughjs/bin/core";
import type { Accessory, Eyes, Mouth, MoodSpec } from "./spec";

const generator = rough.generator();

const INK = "#23232e";
const BODY = "#f6f1e7";
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
      return both((x, y) =>
        generator.ellipse(x - 2, y - 3, 7, 10, solid(seed, INK)),
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
          79,
          6,
          6,
          solid(seed, "#ff8fa3", { strokeWidth: 1.4 }),
        ),
        generator.path("M 44 70 Q 51 77 58 70", line(seed)),
      );
    case "none":
      return [];
  }
}

const star = (x: number, y: number, r: number) =>
  `M ${x} ${y - r} L ${x + r / 4} ${y - r / 4} L ${x + r} ${y} L ${x + r / 4} ${y + r / 4} L ${x} ${y + r} L ${x - r / 4} ${y + r / 4} L ${x - r} ${y} L ${x - r / 4} ${y - r / 4} Z`;

function drawAccessory(kind: Accessory | null, seed: number): PathInfo[] {
  switch (kind) {
    case null:
      return [];
    case "zzz":
      return paths(
        generator.linearPath(
          [
            [72, 28],
            [80, 28],
            [72, 36],
            [80, 36],
          ],
          line(seed, { strokeWidth: 2 }),
        ),
        generator.linearPath(
          [
            [83, 14],
            [89, 14],
            [83, 20],
            [89, 20],
          ],
          line(seed, { strokeWidth: 1.8 }),
        ),
      );
    case "thoughts":
      return paths(
        generator.circle(76, 40, 3, solid(seed, INK)),
        generator.circle(82, 31, 5, solid(seed, INK)),
        generator.circle(89, 20, 8, solid(seed, "#e8eeff")),
      );
    case "magnifier":
      return paths(
        generator.circle(76, 66, 16, solid(seed, "#dff3ff55")),
        generator.linearPath(
          [
            [82, 72],
            [92, 84],
          ],
          line(seed, { strokeWidth: 3.2 }),
        ),
      );
    case "pencil":
      return paths(
        generator.rectangle(6, 62, 16, 20, solid(seed, "#fffdf2")),
        generator.linearPath(
          [
            [70, 74],
            [76, 68],
            [92, 82],
            [86, 88],
            [70, 74],
          ],
          solid(seed, "#ffd45e"),
        ),
      );
    case "hand":
      return paths(
        generator.path("M 76 72 Q 88 66 89 52", line(seed, { strokeWidth: 3 })),
        generator.circle(89, 46, 10, solid(seed, BODY)),
      );
    case "shield":
      return paths(
        generator.path(
          "M 70 46 L 92 46 L 92 62 Q 92 74 81 80 Q 70 74 70 62 Z",
          solid(seed, "#ffd0d4"),
        ),
      );
    case "sparkles":
      return paths(
        generator.path(
          star(14, 30, 7),
          solid(seed, "#ffe27a", { strokeWidth: 1.4 }),
        ),
        generator.path(
          star(88, 34, 6),
          solid(seed, "#ffe27a", { strokeWidth: 1.4 }),
        ),
        generator.path(
          star(82, 10, 5),
          solid(seed, "#ffe27a", { strokeWidth: 1.4 }),
        ),
      );
    case "sweat":
      return paths(
        generator.path(
          "M 74 36 Q 80 44 74 49 Q 68 44 74 36 Z",
          solid(seed, "#8ad0ff"),
        ),
      );
  }
}

export function drawLayers(spec: MoodSpec, seed: number): Layers {
  return {
    body: paths(generator.path(BEAN, solid(seed, BODY, { strokeWidth: 2.6 }))),
    eyes: drawEyes(spec.eyes, seed),
    brow: spec.eyebrow
      ? paths(
          generator.path("M 55 43 L 70 39", line(seed, { strokeWidth: 2.6 })),
        )
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
