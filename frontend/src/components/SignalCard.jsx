import React from "react";
import { Link } from "react-router-dom";

const REGIME_COLORS = {
  WHALE_UP: "border-l-green-500",
  WHALE_DOWN: "border-l-red-500",
  HERD_UP: "border-l-orange-500",
  HERD_DOWN: "border-l-rose-700",
  WASH_PAIRED: "border-l-yellow-500",
  EQUILIBRIUM_TWO_SIDED: "border-l-blue-500",
  DEPLETED: "border-l-gray-500",
  UNKNOWN: "border-l-slate-500",
};

const REGIME_LABELS = {
  WHALE_UP: "Whale ↑", WHALE_DOWN: "Whale ↓",
  HERD_UP: "Herd ↑", HERD_DOWN: "Herd ↓",
  WASH_PAIRED: "Wash ⚠", EQUILIBRIUM_TWO_SIDED: "Equilibrium",
  DEPLETED: "Depleted", UNKNOWN: "Unknown",
};

export default function SignalCard({ sig }) {
  const cls = REGIME_COLORS[sig.regime] || "border-l-slate-500";
  const time = new Date(sig.timestamp_utc * 1000).toLocaleTimeString("en-US", { hour12: false });
  const conf = sig.adjusted_confidence ?? sig.confidence ?? 0;
  const cvm = sig.cross_venue_multiplier ?? 1.0;

  return (
    <Link
      to={`/signal/${sig.signal_id}`}
      className={`block bg-slate-900/70 border-l-4 ${cls} rounded-r p-3 mb-2 hover:bg-slate-900 transition`}
    >
      <div className="flex items-start justify-between">
        <div>
          <div className="font-mono text-sm font-semibold">
            {REGIME_LABELS[sig.regime] || sig.regime}
            <span className="text-slate-400 ml-2 text-xs">{sig.asset}-USD on {sig.venue}</span>
          </div>
          <div className="text-xs text-slate-500 mt-1">
            dipole {sig.mean_dipole?.toFixed(3)} · conf {(conf * 100).toFixed(0)}%
            {cvm > 1.0 && <span className="text-green-400 ml-2">✓ cross-venue</span>}
            {cvm < 1.0 && <span className="text-yellow-500 ml-2">✗ single-venue</span>}
          </div>
        </div>
        <span className="text-xs text-slate-500 font-mono">{time}</span>
      </div>
      <div className="text-xs text-slate-400 mt-2 line-clamp-2">{sig.playbook}</div>
    </Link>
  );
}
