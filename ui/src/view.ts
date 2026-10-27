// Which of the three HUD shapes is showing. Derived from the event state plus
// one UI-only flag (the user opened the panel); never stored on its own.
import type { HaloState } from "./state/reducer";

export type View = "bar" | "card" | "panel";

export const SIZES: Record<View, [number, number]> = {
  bar: [260, 44],
  card: [380, 140],
  panel: [640, 360],
};

export function selectView(halo: HaloState, expanded: boolean): View {
  if (halo.pendingApprovals.length > 0) return "card"; // a permission request always wins
  return expanded ? "panel" : "bar";
}
