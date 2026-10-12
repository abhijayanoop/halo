// The one zustand store. Its halo slice is only ever changed by the event
// reducer; `connection` is the only other thing kept here.
import { create } from "zustand";
import type { ConnectionStatus } from "../connection";
import type { HaloEvent } from "../types/generated/HaloEvent";
import { type HaloState, initialState, reduce } from "./reducer";

interface Store {
  halo: HaloState;
  connection: ConnectionStatus;
  apply: (event: HaloEvent) => void;
  setConnection: (status: ConnectionStatus) => void;
  reset: () => void;
}

export const useStore = create<Store>((set) => ({
  halo: initialState,
  connection: "connecting",
  apply: (event) => set((s) => ({ halo: reduce(s.halo, event) })),
  setConnection: (connection) => set({ connection }),
  reset: () => set({ halo: initialState }),
}));
