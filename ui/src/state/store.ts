// The one zustand store. `halo` is only ever changed by the event reducer.
// The rest is UI-only: the connection light and whether the user opened the panel.
import { create } from "zustand";
import type { ConnectionStatus } from "../connection";
import type { HaloEvent } from "../types/generated/HaloEvent";
import { type HaloState, initialState, reduce } from "./reducer";

interface Store {
  halo: HaloState;
  connection: ConnectionStatus;
  expanded: boolean;
  apply: (event: HaloEvent) => void;
  setConnection: (status: ConnectionStatus) => void;
  setExpanded: (expanded: boolean) => void;
  reset: () => void;
}

export const useStore = create<Store>((set) => ({
  halo: initialState,
  connection: "connecting",
  expanded: false,
  apply: (event) => set((s) => ({ halo: reduce(s.halo, event) })),
  setConnection: (connection) => set({ connection }),
  setExpanded: (expanded) => set({ expanded }),
  reset: () => set({ halo: initialState }),
}));
