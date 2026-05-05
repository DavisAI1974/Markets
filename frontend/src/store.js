import { create } from "zustand";

const PRACTICE_KEY = "marketsWatch.practiceMode";

// Default to practice mode ON for safety. Users explicitly opt into live
// trading via the header toggle; this preference is per-device, persisted
// in localStorage so it survives reloads.
function loadPracticeMode() {
  try {
    const v = localStorage.getItem(PRACTICE_KEY);
    if (v === null) return true;     // first run: practice ON
    return v !== "false";
  } catch {
    return true;
  }
}

export const useStore = create((set, get) => ({
  statuses: [],            // current regime per (asset, venue)
  signals: [],             // recent signal events
  connected: false,
  lastError: null,
  practiceMode: loadPracticeMode(),

  setStatuses: (statuses) => set({ statuses }),
  setSignals: (signals) => set({ signals }),
  prependSignal: (sig) => set({ signals: [sig, ...get().signals].slice(0, 200) }),
  setConnected: (connected) => set({ connected }),
  setError: (lastError) => set({ lastError }),
  setPracticeMode: (on) => {
    try { localStorage.setItem(PRACTICE_KEY, on ? "true" : "false"); } catch {}
    set({ practiceMode: !!on });
  },
}));
