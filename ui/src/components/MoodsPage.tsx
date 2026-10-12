import { HaloMascot } from "../character/HaloMascot";
import { moodSpec } from "../character/spec";
import { MOODS } from "../state/reducer";

/** Dev-only sheet of all 13 moods side by side, for tuning and for the video. */
export function MoodsPage() {
  return (
    <main className="grid h-full grid-cols-4 gap-4 overflow-y-auto bg-slate-900 p-6">
      {MOODS.map((mood) => {
        const spec = moodSpec(mood);
        return (
          <figure
            key={mood}
            data-testid="mood-figure"
            data-mood={mood}
            className="flex flex-col items-center gap-1 rounded-xl border border-white/10 p-3"
          >
            <div data-testid={`mood-figure-${mood}`} className="contents">
              <HaloMascot
                mood={mood}
                agents={mood === "delegating" ? 3 : 0}
                progress={0.6}
                size={120}
              />
              <figcaption className="text-center text-sm text-slate-100">
                {spec.label}
                <span className="block text-xs text-slate-500">
                  {spec.ring}
                </span>
              </figcaption>
            </div>
          </figure>
        );
      })}
    </main>
  );
}
