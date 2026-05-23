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
  driftAlerts: [],         // recent drift_alert SSE events (newest first)
  connected: false,
  lastError: null,
  practiceMode: loadPracticeMode(),
  autoTradeSettings: {
    enabled: false,
    practice: true,
    tolerance: "balanced",
    profiles: ["early_probe", "confirmed_follow"],
    min_readiness: 65,
    max_open_trades: 3,
    base_notional_usd: 1000,
  },
  openSignalDetailId: null,  // when set, SignalDetailSheet renders as a bottom-sheet overlay

  setStatuses: (statuses) => set({ statuses }),
  setSignals: (signals) => set({ signals }),
  prependSignal: (sig) => set({ signals: [sig, ...get().signals].slice(0, 200) }),
  setDriftAlerts: (driftAlerts) => set({ driftAlerts }),
  prependDriftAlert: (a) => set({ driftAlerts: [a, ...get().driftAlerts].slice(0, 60) }),
  setConnected: (connected) => set({ connected }),
  setError: (lastError) => set({ lastError }),
  setAutoTradeSettings: (autoTradeSettings) => set({ autoTradeSettings }),
  setPracticeMode: (on) => {
    try { localStorage.setItem(PRACTICE_KEY, on ? "true" : "false"); } catch {}
    set({ practiceMode: !!on });
  },
  openSignalSheet: (id) => set({ openSignalDetailId: id }),
  closeSignalSheet: () => set({ openSignalDetailId: null }),
}));
