import { HaloMascot } from "../character/HaloMascot";
import type { HaloState } from "../state/reducer";

export function runningAgents(halo: HaloState): number {
  const run = halo.activeRunId ? halo.runs[halo.activeRunId] : undefined;
  return run
    ? Object.values(run.agents).filter((a) => a.status === "running").length
    : 0;
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

  return (
    <button
      type="button"
      aria-label="Open Halo"
      onClick={onExpand}
      className="flex h-[44px] w-[260px] items-center gap-2 rounded-[22px] border border-white/10 bg-slate-900/80 px-2 text-left shadow-lg backdrop-blur"
    >
      <HaloMascot
        mood={halo.mood}
        agents={agents}
        progress={progress ? progress.step / progress.of : null}
        size={36}
      />
      <span
        data-testid="status-line"
        className="min-w-0 flex-1 truncate text-[13px] text-slate-100"
      >
        {halo.statusLine}
      </span>
      {progress && (
        <span
          data-testid="step-progress"
          className="text-[11px] tabular-nums text-slate-400"
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
              className="h-1.5 w-1.5 rounded-full bg-violet-400"
            />
          ))}
        </span>
      )}
    </button>
  );
}
