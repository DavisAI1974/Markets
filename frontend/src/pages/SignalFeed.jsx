import React, { useState, useMemo } from "react";
import { useStore } from "../store.js";
import SignalCard from "../components/SignalCard.jsx";

const REGIME_OPTS = [
  "WHALE_UP", "WHALE_DOWN", "HERD_UP", "HERD_DOWN",
  "WASH_PAIRED", "EQUILIBRIUM_EXTREME_DEMO",
];

export default function SignalFeed() {
  const signals = useStore((s) => s.signals);
  const [assetFilter, setAssetFilter] = useState("all");
  const [venueFilter, setVenueFilter] = useState("all");
  const [regimeFilter, setRegimeFilter] = useState("all");
  const [confirmedOnly, setConfirmedOnly] = useState(false);

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

  const assets = useMemo(() => Array.from(new Set((signals || []).map((s) => s.asset))).sort(), [signals]);
  const venues = useMemo(() => Array.from(new Set((signals || []).map((s) => s.venue))).sort(), [signals]);
  const regimes = useMemo(() => Array.from(new Set((signals || []).map((s) => s.regime))).sort(), [signals]);

  return (
    <div>
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
        <Pill active={regimeFilter === "all"} onClick={() => setRegimeFilter("all")}>regime: all</Pill>
        {regimes.filter((r) => REGIME_OPTS.includes(r)).map((r) => (
          <Pill key={r} active={regimeFilter === r} onClick={() => setRegimeFilter(r)}>
            {r.replace(/_/g, " ").replace("EQUILIBRIUM EXTREME DEMO", "EQ-EXT")}
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
        <div className="text-slate-500 text-sm py-8 text-center italic">
          {signals?.length === 0
            ? "No signals yet. Most market activity is healthy two-sided trading. Signals fire when we detect a big buyer, big seller, buying or selling cascade, or wash pattern."
            : "No signals match the current filters."}
        </div>
      ) : (
        filtered.map((sig) => <SignalCard key={sig.signal_id} sig={sig} />)
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
