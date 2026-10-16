import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type { Mood } from "../state/reducer";
import { BODY_GRADIENT, type Layers, type Shape, drawLayers } from "./draw";
import { type Motion, moodSpec } from "./spec";

const MAX_MINI_HALOS = 4;
const ORBIT = { cx: 50, cy: 17, rx: 46, ry: 9, steps: 16 };
const EYE_TRAVEL = { x: 3.2, y: 2.4 }; // how far the eyes can look, in viewBox units
const SPRING = { type: "spring", stiffness: 420, damping: 24 } as const;

/** Keyframes that carry a mini-halo once around a flat ellipse above the head,
 *  starting `phase` (0..1) of the way round. It never crosses the face. */
function orbitFrames(phase: number) {
  const angles = Array.from(
    { length: ORBIT.steps + 1 },
    (_, k) => 2 * Math.PI * (phase + k / ORBIT.steps),
  );
  return {
    cx: angles.map((a) => ORBIT.cx + ORBIT.rx * Math.cos(a)),
    cy: angles.map((a) => ORBIT.cy + ORBIT.ry * Math.sin(a)),
  };
}

/** A random blink every 3 to 6 seconds. */
function useBlink(enabled: boolean): boolean {
  const [blinking, setBlinking] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    let timer: ReturnType<typeof setTimeout>;
    const schedule = () => {
      timer = setTimeout(
        () => {
          setBlinking(true);
          timer = setTimeout(() => {
            setBlinking(false);
            schedule();
          }, 120);
        },
        3000 + Math.random() * 3000,
      );
    };
    schedule();
    return () => clearTimeout(timer);
  }, [enabled]);
  return blinking;
}

const clamp = (n: number) =>
  Math.max(-1, Math.min(1, Number.isFinite(n) ? n : 0));

function Shapes({
  layer,
  name,
}: {
  layer: Layers[keyof Layers];
  name: string;
}) {
  return (
    <g data-layer={name}>
      {layer.map((p: Shape, i) => (
        <path
          // biome-ignore lint/suspicious/noArrayIndexKey: paths are positional
          key={i}
          d={p.d}
          stroke={p.stroke}
          strokeWidth={p.strokeWidth}
          fill={p.fill ?? "none"}
          opacity={p.opacity}
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      ))}
    </g>
  );
}

function ringMotion(motionKind: Motion, reduced: boolean) {
  if (reduced) return {};
  switch (motionKind) {
    case "spin":
      return {
        animate: { scaleX: [1, 0.6, 1] },
        transition: {
          duration: 3.2,
          repeat: Infinity,
          ease: "easeInOut" as const,
        },
      };
    case "pulse":
      return {
        animate: { scale: [1, 1.12, 1], opacity: [1, 0.7, 1] },
        transition: {
          duration: 1.1,
          repeat: Infinity,
          ease: "easeInOut" as const,
        },
      };
    default:
      return {};
  }
}

function bodyMotion(motionKind: Motion, busy: boolean, reduced: boolean) {
  if (reduced) return {};
  if (busy) {
    // Working: a small, steady sway, as if humming along.
    return {
      animate: { rotate: [-1.6, 1.6, -1.6], y: [0, -1.2, 0] },
      transition: {
        duration: 1.8,
        repeat: Infinity,
        ease: "easeInOut" as const,
      },
    };
  }
  switch (motionKind) {
    case "bounce":
      return {
        animate: { y: [0, -9, 0, -5, 0] },
        transition: { duration: 0.9, repeat: 2 },
      };
    case "squash":
      return {
        animate: { scaleY: [0.82, 1.12, 1], scaleX: [1.1, 0.95, 1] },
        transition: { duration: 0.6 },
      };
    case "slow":
      return {
        animate: { scale: [1, 1.03, 1] },
        transition: {
          duration: 6,
          repeat: Infinity,
          ease: "easeInOut" as const,
        },
      };
    default:
      return {
        animate: { scale: [1, 1.03, 1] },
        transition: {
          duration: 3,
          repeat: Infinity,
          ease: "easeInOut" as const,
        },
      };
  }
}

export interface HaloMascotProps {
  mood: Mood;
  /** Running sub-agents: one orbiting mini-halo each (at most four drawn). */
  agents?: number;
  /** 0..1, only drawn as the progress ring in the focused mood. */
  progress?: number | null;
  /** Where the eyes look, each -1..1 (x right, y down). Straight ahead if unset. */
  gaze?: { x: number; y: number } | null;
  size?: number;
}

export function HaloMascot({
  mood,
  agents = 0,
  progress = null,
  gaze = null,
  size = 96,
}: HaloMascotProps) {
  const spec = moodSpec(mood);
  const reduced = useReducedMotion() ?? false;
  const blinking = useBlink(spec.eyes === "open" || spec.eyes === "wide");
  const layers = useMemo(() => drawLayers(spec), [spec]);
  const miniCount = Math.min(Math.max(agents, 0), MAX_MINI_HALOS);
  const progressValue = progress ?? 0.35;
  const gx = clamp(gaze?.x ?? 0);
  const gy = clamp(gaze?.y ?? 0);
  const glowPx = 2 + spec.glow * 9;

  return (
    <motion.svg
      role="img"
      aria-label={spec.label}
      data-mood={mood}
      data-busy={spec.busy ? "true" : "false"}
      viewBox="0 0 100 100"
      width={size}
      height={size}
      style={{ overflow: "visible" }}
    >
      <defs>
        <linearGradient id="halo-body" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={BODY_GRADIENT.top} />
          <stop offset="1" stopColor={BODY_GRADIENT.bottom} />
        </linearGradient>
      </defs>

      {/* A new mood pops in with a spring instead of snapping. */}
      <motion.g
        key={mood}
        initial={reduced ? false : { scale: 0.93 }}
        animate={{ scale: 1 }}
        transition={SPRING}
        style={{ transformBox: "fill-box", transformOrigin: "50% 100%" }}
      >
        <motion.g
          style={{ transformBox: "fill-box", transformOrigin: "50% 100%" }}
          {...bodyMotion(spec.motion, spec.busy, reduced)}
        >
          <Shapes layer={layers.body} name="body" />
          <motion.g
            data-layer="eyes"
            data-gaze-x={gx}
            data-gaze-y={gy}
            animate={{ x: gx * EYE_TRAVEL.x, y: gy * EYE_TRAVEL.y }}
            transition={SPRING}
          >
            <motion.g
              style={{ transformBox: "fill-box", transformOrigin: "50% 50%" }}
              animate={{ scaleY: blinking ? 0.1 : 1 }}
              transition={{ duration: 0.08 }}
            >
              {layers.eyes.map((p, i) => (
                <path
                  // biome-ignore lint/suspicious/noArrayIndexKey: paths are positional
                  key={i}
                  d={p.d}
                  stroke={p.stroke}
                  strokeWidth={p.strokeWidth}
                  fill={p.fill ?? "none"}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              ))}
            </motion.g>
          </motion.g>
          <Shapes layer={layers.brow} name="brow" />
          <Shapes layer={layers.mouth} name="mouth" />
          {spec.accessory && (
            <g data-accessory={spec.accessory}>
              <Shapes layer={layers.accessory} name="accessory" />
            </g>
          )}
        </motion.g>
      </motion.g>

      <motion.g
        style={{
          transformBox: "fill-box",
          transformOrigin: "50% 50%",
          filter: `drop-shadow(0 0 ${glowPx}px ${spec.ring})`,
        }}
        opacity={spec.ringStyle === "progress" ? 0.25 : 1}
        {...ringMotion(spec.motion, reduced)}
      >
        <Shapes layer={layers.ring} name="ring" />
      </motion.g>

      {spec.ringStyle === "progress" && (
        <ellipse
          data-layer="progress"
          cx={50}
          cy={14}
          rx={22}
          ry={6.5}
          fill="none"
          stroke={spec.ring}
          strokeWidth={3.8}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={`${progressValue} 1`}
        />
      )}

      {miniCount > 0 &&
        Array.from({ length: miniCount }, (_, i) => {
          const frames = orbitFrames(i / miniCount);
          return (
            <motion.ellipse
              // biome-ignore lint/suspicious/noArrayIndexKey: fixed small set
              key={i}
              data-testid="mini-halo"
              cx={frames.cx[0]}
              cy={frames.cy[0]}
              rx={10}
              ry={3.4}
              fill="none"
              stroke={spec.ring}
              strokeWidth={2.6}
              animate={reduced ? {} : frames}
              transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
            />
          );
        })}
    </motion.svg>
  );
}
