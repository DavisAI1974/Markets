import { create } from "zustand";

export const useStore = create((set, get) => ({
  statuses: [],            // current regime per (asset, venue)
  signals: [],             // recent signal events
  connected: false,
  lastError: null,

  setStatuses: (statuses) => set({ statuses }),
  setSignals: (signals) => set({ signals }),
  prependSignal: (sig) => set({ signals: [sig, ...get().signals].slice(0, 200) }),
  setConnected: (connected) => set({ connected }),
  setError: (lastError) => set({ lastError }),
}));
