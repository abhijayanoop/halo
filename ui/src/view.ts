// Which of the three HUD shapes is showing. Derived from the event state plus
// one UI-only flag (the user opened the panel); never stored on its own.
import type { HaloState } from "./state/reducer";

export type View = "bar" | "card" | "panel" | "brief" | "result";

export const SIZES: Record<View, [number, number]> = {
  bar: [260, 44],
  card: [380, 140],
  panel: [640, 360],
  brief: [460, 480],
  result: [500, 560],
};

export function selectView(halo: HaloState, expanded: boolean): View {
  const first = halo.pendingApprovals[0];
  if (first?.kind === "code.brief") return "brief"; // a card always wins
  if (first?.kind === "code.result") return "result";
  if (halo.pendingApprovals.length > 0) return "card"; // a permission request always wins
  return expanded ? "panel" : "bar";
}
