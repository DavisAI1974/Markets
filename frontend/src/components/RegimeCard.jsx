import React from "react";

const REGIME_STYLES = {
  EQUILIBRIUM_TWO_SIDED: { bg: "bg-blue-950/40", border: "border-blue-700", chip: "bg-blue-700", label: "Equilibrium" },
  WHALE_UP: { bg: "bg-green-950/40", border: "border-green-700", chip: "bg-green-700", label: "Whale ↑" },
  WHALE_DOWN: { bg: "bg-red-950/40", border: "border-red-700", chip: "bg-red-700", label: "Whale ↓" },
  HERD_UP: { bg: "bg-orange-950/40", border: "border-orange-700", chip: "bg-orange-600", label: "Herd ↑" },
  HERD_DOWN: { bg: "bg-rose-950/40", border: "border-rose-700", chip: "bg-rose-700", label: "Herd ↓" },
  WASH_PAIRED: { bg: "bg-yellow-950/40", border: "border-yellow-700", chip: "bg-yellow-700", label: "Wash ⚠" },
  DEPLETED: { bg: "bg-gray-900/60", border: "border-gray-600", chip: "bg-gray-600", label: "Depleted" },
  UNKNOWN: { bg: "bg-slate-900/60", border: "border-slate-700", chip: "bg-slate-700", label: "Unknown" },
};

export default function RegimeCard({ status }) {
  const s = REGIME_STYLES[status.regime] || REGIME_STYLES.UNKNOWN;
  const conf = status.adjusted_confidence ?? status.confidence ?? 0;
  const confPct = (conf * 100).toFixed(0);
  const cvm = status.cross_venue_multiplier ?? 1.0;
  const cvmIcon = cvm > 1.0 ? "✓ confirmed" : cvm < 1.0 ? "✗ disagreement" : "—";
  const lastUpdate = status.last_update_utc
    ? new Date(status.last_update_utc * 1000).toLocaleTimeString("en-US", { hour12: false })
    : "—";

  return (
    <div className={`rounded-lg border ${s.border} ${s.bg} p-4 mb-3`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="font-mono text-base font-semibold">
            {status.asset}-USD <span className="text-slate-400 text-sm">on {status.venue}</span>
          </div>
        </div>
        <span className={`px-2 py-1 rounded text-xs font-semibold ${s.chip}`}>{s.label}</span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
        <Metric label="dipole" value={status.mean_dipole?.toFixed(3) ?? "—"} />
        <Metric label="real vol" value={(status.realized_vol * 1e4)?.toFixed(1) + " bp" ?? "—"} />
        <Metric label="conf" value={`${confPct}%`} />
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
        <span>cross-venue: {cvmIcon}</span>
        <span>{lastUpdate} UTC</span>
      </div>
      {status.notes && status.notes.length > 0 && (
        <div className="mt-2 text-xs text-slate-400 italic line-clamp-2">{status.notes[0]}</div>
      )}
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="bg-slate-950/60 rounded px-2 py-1">
      <div className="text-slate-500 text-[10px] uppercase tracking-wide">{label}</div>
      <div className="font-mono text-sm">{value}</div>
    </div>
  );
}
