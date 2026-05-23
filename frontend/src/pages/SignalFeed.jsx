import React, { useState, useMemo, useRef, useEffect } from "react";
import { useStore } from "../store.js";
import SignalCard from "../components/SignalCard.jsx";
import { EmptyState } from "../components/LoadingSkeleton.jsx";
import { usePullToRefresh, PullIndicator } from "../usePullToRefresh.jsx";
import { fetchSignals } from "../api.js";

const REGIME_OPTS = [
  "WHALE_UP", "WHALE_DOWN", "HERD_UP", "HERD_DOWN",
  "WASH_PAIRED", "EQUILIBRIUM_EXTREME_DEMO",
];

const SETUP_LABELS = {
  WHALE_UP: "whale buyer",
  WHALE_DOWN: "whale seller",
  HERD_UP: "herd buying",
  HERD_DOWN: "herd selling",
  WASH_PAIRED: "suspect flow",
  EQUILIBRIUM_EXTREME_DEMO: "equilibrium",
};

export default function SignalFeed() {
  const signals = useStore((s) => s.signals);
  const setSignals = useStore((s) => s.setSignals);
  const ptr = usePullToRefresh(async () => {
    try {
      const j = await fetchSignals(100);
      setSignals(j.signals || []);
    } catch {}
  });
  const [assetFilter, setAssetFilter] = useState("all");
  const [venueFilter, setVenueFilter] = useState("all");
  const [regimeFilter, setRegimeFilter] = useState("all");
  const [confirmedOnly, setConfirmedOnly] = useState(false);

  // Track which signal_ids we've seen so newly-arrived ones get the
  // slide-in + cascade-pulse animation only on first render.
  const seenIds = useRef(new Set());
  const [, force] = useState(0);
  useEffect(() => {
    if (!signals) return;
    let added = false;
    for (const s of signals) {
      if (s && s.signal_id && !seenIds.current.has(s.signal_id)) {
        seenIds.current.add(s.signal_id);
        added = true;
      }
    }
    if (added) force((x) => x + 1);
  }, [signals]);

  const filtered = useMemo(() => {
    if (!signals) return [];
    return signals.filter((s) => {
      if (assetFilter !== "all" && s.asset !== assetFilter) return false;
      if (venueFilter !== "all" && s.venue !== venueFilter) return false;
      if (regimeFilter !== "all" && s.regime !== regimeFilter) return false;
      if (confirmedOnly && (s.cross_venue_multiplier || 1.0) <= 1.0) return false;
      return true;
    });
  }, [signals, assetFilter, venueFilter, regimeFilter, confirmedOnly]);

  // The first signal in the unfiltered list is "freshest" — only animate
  // it if it just arrived (i.e. not yet seen for >1s). Use a small ref
  // tracking when each id was first seen.
  const firstSeenAt = useRef(new Map());
  for (const s of signals || []) {
    if (s && s.signal_id && !firstSeenAt.current.has(s.signal_id)) {
      firstSeenAt.current.set(s.signal_id, Date.now());
    }
  }

  const assets = useMemo(() => Array.from(new Set((signals || []).map((s) => s.asset))).sort(), [signals]);
  const venues = useMemo(() => Array.from(new Set((signals || []).map((s) => s.venue))).sort(), [signals]);
  const regimes = useMemo(() => Array.from(new Set((signals || []).map((s) => s.regime))).sort(), [signals]);

  return (
    <div>
      <PullIndicator {...ptr} />
      <div className="flex flex-wrap gap-1.5 mb-3 items-center">
        <Pill active={assetFilter === "all"} onClick={() => setAssetFilter("all")}>asset: all</Pill>
        {assets.map((a) => (
          <Pill key={a} active={assetFilter === a} onClick={() => setAssetFilter(a)}>{a}</Pill>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5 mb-3 items-center">
        <Pill active={venueFilter === "all"} onClick={() => setVenueFilter("all")}>venue: all</Pill>
        {venues.map((v) => (
          <Pill key={v} active={venueFilter === v} onClick={() => setVenueFilter(v)}>{v}</Pill>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5 mb-3 items-center">
        <Pill active={regimeFilter === "all"} onClick={() => setRegimeFilter("all")}>setup: all</Pill>
        {regimes.filter((r) => REGIME_OPTS.includes(r)).map((r) => (
          <Pill key={r} active={regimeFilter === r} onClick={() => setRegimeFilter(r)}>
            {SETUP_LABELS[r] || "market read"}
          </Pill>
        ))}
        <Pill active={confirmedOnly} onClick={() => setConfirmedOnly(!confirmedOnly)} accent="green">
          ✓ cross-venue
        </Pill>
      </div>

      <h2 className="text-xs uppercase tracking-wider text-slate-500 mb-2 px-1">
        {filtered.length} of {signals?.length || 0} signals
      </h2>
      {filtered.length === 0 ? (
        signals?.length === 0 ? (
          <EmptyState
            icon="📡"
            title="No signals yet"
            body="Most market activity is equilibrium. Signals fire when we detect a whale buyer, whale seller, herd move, or wash pattern. Leave this open and you'll see them arrive in real time."
          />
        ) : (
          <EmptyState
            icon="🔍"
            title="No signals match"
            body="Try clearing one of the filters above."
          />
        )
      ) : (
        filtered.map((sig) => {
          const seenAt = firstSeenAt.current.get(sig.signal_id) || 0;
          const isFresh = (Date.now() - seenAt) < 1500;
          return <SignalCard key={sig.signal_id} sig={sig} isFresh={isFresh} />;
        })
      )}
    </div>
  );
}

function Pill({ active, onClick, children, accent }) {
  const accentCls = accent === "green"
    ? (active ? "bg-green-700 border-green-600" : "border-slate-700 hover:border-green-700")
    : (active ? "bg-slate-700 border-slate-600" : "border-slate-800 hover:border-slate-600");
  return (
    <button
      onClick={onClick}
      className={`px-2 py-0.5 rounded text-xs border ${accentCls} text-slate-200 transition`}
    >
      {children}
    </button>
  );
}
