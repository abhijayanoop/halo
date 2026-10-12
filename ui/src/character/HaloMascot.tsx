import { motion, useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useState } from "react";
import type { Mood } from "../state/reducer";
import { type Layers, drawLayers } from "./draw";
import { type Motion, moodSpec } from "./spec";

const BOIL_MS = 125; // ~8 redraws a second
const MAX_MINI_HALOS = 4;

/** Re-seed the sketch ~8 times a second while `active`, so the line shimmers. */
function useBoil(active: boolean): number {
  const [seed, setSeed] = useState(1);
  useEffect(() => {
    if (!active) {
      setSeed(1);
      return;
    }
    const timer = setInterval(() => setSeed((s) => (s % 1000) + 1), BOIL_MS);
    return () => clearInterval(timer);
  }, [active]);
  return seed;
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

const group = (layer: Layers[keyof Layers], name: string) => (
  <g data-layer={name}>
    {layer.map((p, i) => (
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
  </g>
);

function ringMotion(motionKind: Motion, reduced: boolean) {
  if (reduced) return {};
  switch (motionKind) {
    case "spin":
      return {
        animate: { scaleX: [1, 0.35, 1] },
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

function bodyMotion(motionKind: Motion, reduced: boolean) {
  if (reduced) return {};
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
  size?: number;
}

export function HaloMascot({
  mood,
  agents = 0,
  progress = null,
  size = 96,
}: HaloMascotProps) {
  const spec = moodSpec(mood);
  const reduced = useReducedMotion() ?? false;
  const seed = useBoil(spec.busy && !reduced);
  const blinking = useBlink(spec.eyes === "open" || spec.eyes === "wide");
  const layers = useMemo(() => drawLayers(spec, seed), [spec, seed]);
  const miniCount = Math.min(Math.max(agents, 0), MAX_MINI_HALOS);
  const progressValue = progress ?? 0.35;

  return (
    <motion.svg
      role="img"
      aria-label={spec.label}
      data-mood={mood}
      viewBox="0 0 100 100"
      width={size}
      height={size}
      style={{ overflow: "visible" }}
    >
      <motion.g
        style={{ transformBox: "fill-box", transformOrigin: "50% 100%" }}
        {...bodyMotion(spec.motion, reduced)}
      >
        {group(layers.body, "body")}
        <motion.g
          style={{ transformBox: "fill-box", transformOrigin: "50% 50%" }}
          animate={{ scaleY: blinking ? 0.1 : 1 }}
          transition={{ duration: 0.08 }}
        >
          {group(layers.eyes, "eyes")}
        </motion.g>
        {group(layers.brow, "brow")}
        {group(layers.mouth, "mouth")}
        {spec.accessory && (
          <g data-accessory={spec.accessory}>
            {group(layers.accessory, "accessory")}
          </g>
        )}
      </motion.g>

      <motion.g
        style={{ transformBox: "fill-box", transformOrigin: "50% 50%" }}
        opacity={spec.ringStyle === "progress" ? 0.35 : 1}
        {...ringMotion(spec.motion, reduced)}
      >
        {group(layers.ring, "ring")}
      </motion.g>

      {spec.ringStyle === "progress" && (
        <ellipse
          data-layer="progress"
          cx={50}
          cy={14}
          rx={42 / 2}
          ry={12 / 2}
          fill="none"
          stroke={spec.ring}
          strokeWidth={3.6}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={`${progressValue} 1`}
        />
      )}

      {miniCount > 0 && (
        <motion.g
          style={{ transformOrigin: "50px 56px" }}
          animate={reduced ? {} : { rotate: 360 }}
          transition={{ duration: 4, repeat: Infinity, ease: "linear" }}
        >
          {Array.from({ length: miniCount }, (_, i) => {
            const angle = (i / miniCount) * 2 * Math.PI;
            const x = 50 + 46 * Math.cos(angle);
            const y = 56 + 40 * Math.sin(angle);
            return (
              <ellipse
                // biome-ignore lint/suspicious/noArrayIndexKey: fixed small set
                key={i}
                data-testid="mini-halo"
                cx={x}
                cy={y}
                rx={7}
                ry={2.4}
                fill="none"
                stroke={spec.ring}
                strokeWidth={2}
              />
            );
          })}
        </motion.g>
      )}
    </motion.svg>
  );
}
