import { motion } from "framer-motion";
import { type CSSProperties, useEffect, useRef, useState } from "react";
import { HaloMascot } from "../character/HaloMascot";
import { moodSpec } from "../character/spec";
import type { HaloState } from "../state/reducer";

export function runningAgents(halo: HaloState): number {
  const run = halo.activeRunId ? halo.runs[halo.activeRunId] : undefined;
  return run
    ? Object.values(run.agents).filter((a) => a.status === "running").length
    : 0;
}

type Gaze = { x: number; y: number } | null;
const clamp = (n: number) => Math.max(-1, Math.min(1, n));

/** Where the pointer is, relative to the mascot, as a -1..1 gaze. Only moves
 *  while the pointer is over the window (the page gets no events outside it). */
export function useGaze(target: React.RefObject<HTMLElement | null>): Gaze {
  const [gaze, setGaze] = useState<Gaze>(null);
  useEffect(() => {
    const onMove = (event: MouseEvent) => {
      const box = target.current?.getBoundingClientRect();
      const cx = box ? box.left + box.width / 2 : 0;
      const cy = box ? box.top + box.height / 2 : 0;
      setGaze({
        x: clamp((event.clientX - cx) / 160),
        y: clamp((event.clientY - cy) / 40),
      });
    };
    const onLeave = () => setGaze(null);
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseleave", onLeave, true);
    return () => {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseleave", onLeave, true);
    };
  }, [target]);
  return gaze;
}

export function CollapsedBar({
  halo,
  onExpand,
}: {
  halo: HaloState;
  onExpand: () => void;
}) {
  const run = halo.activeRunId ? halo.runs[halo.activeRunId] : undefined;
  const live = run && (run.status === "running" || run.status === "paused");
  const progress = live ? run.progress : null;
  const agents = runningAgents(halo);
  const spec = moodSpec(halo.mood);
  const mascotBox = useRef<HTMLSpanElement>(null);
  const gaze = useGaze(mascotBox);

  return (
    <motion.button
      type="button"
      aria-label="Open Halo"
      data-mood={halo.mood}
      onClick={onExpand}
      whileHover={{ scale: 1.012 }}
      whileTap={{ scale: 0.985 }}
      transition={{ type: "spring", stiffness: 500, damping: 30 }}
      style={{ "--ring": spec.ring } as CSSProperties}
      className="glass relative flex h-[44px] w-[260px] cursor-pointer items-center gap-2 rounded-[22px] px-2 text-left"
    >
      <span ref={mascotBox} className="flex h-9 w-9 shrink-0 items-center">
        <HaloMascot
          mood={halo.mood}
          agents={agents}
          progress={progress ? progress.step / progress.of : null}
          gaze={gaze}
          size={36}
        />
      </span>

      <motion.span
        // A new line fades up into place instead of snapping.
        key={halo.statusLine}
        data-testid="status-line"
        initial={{ opacity: 0, y: 5 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.22 }}
        className="min-w-0 flex-1 truncate text-[13px] font-medium text-ink"
      >
        {halo.statusLine}
      </motion.span>

      {progress && (
        <span
          data-testid="step-progress"
          className="font-mono text-[11px] tabular-nums text-ink-dim"
        >
          {progress.step}/{progress.of}
        </span>
      )}
      {agents > 0 && (
        <span className="flex gap-1" aria-label={`${agents} helpers running`}>
          {Array.from({ length: agents }, (_, i) => (
            <span
              // biome-ignore lint/suspicious/noArrayIndexKey: identical dots
              key={i}
              data-testid="agent-dot"
              className="h-1.5 w-1.5 animate-pulse rounded-full"
              style={{ background: spec.ring }}
            />
          ))}
        </span>
      )}

      {progress && (
        <span
          role="progressbar"
          aria-label="Step progress"
          aria-valuemin={0}
          aria-valuenow={progress.step}
          aria-valuemax={progress.of}
          className="absolute inset-x-5 bottom-[3px] h-[2px] overflow-hidden rounded-full bg-white/10"
        >
          <motion.span
            className="block h-full rounded-full"
            style={{ background: spec.ring }}
            animate={{ width: `${(progress.step / progress.of) * 100}%` }}
            transition={{ type: "spring", stiffness: 200, damping: 26 }}
          />
        </span>
      )}
    </motion.button>
  );
}
