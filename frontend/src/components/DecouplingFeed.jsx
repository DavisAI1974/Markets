import React from "react";

const SEV = {
  critical: "bg-red-900/60 text-red-200 border-red-700",
  warning: "bg-orange-900/50 text-orange-200 border-orange-700",
  info: "bg-slate-800 text-slate-300 border-slate-700",
};

/**
 * DecouplingFeed — coupling-collapse events on the strongest cross-venue pair per asset.
 * A previously-coupled pair whose lag-0 coupling drops below its rolling baseline is a
 * tradeable dislocation. Reads /api/decoupling.
 */
export default function DecouplingFeed({ data }) {
  if (!data) return <div className="text-slate-500 text-xs italic">loading…</div>;
  const events = data.events || [];
  if (events.length === 0) {
    return <div className="text-slate-500 text-xs italic">no decoupling events</div>;
  }
  return (
    <div className="space-y-1.5">
      <div className="text-[10px] text-slate-500">{data.n_total} total events (most recent first)</div>
      {events.map((e, i) => {
        const cls = SEV[e.severity] || SEV.info;
        const when = new Date(e.ts * 1000).toLocaleString("en-US", { hour12: false });
        return (
          <div key={i} className={`rounded border px-3 py-2 text-xs font-mono flex items-center justify-between ${cls}`}>
            <div>
              <div>{e.pair}</div>
              <div className="text-[10px] opacity-70">{when}</div>
            </div>
            <div className="text-right">
              <div>cc {e.cc.toFixed(3)} <span className="opacity-60">vs base {e.baseline.toFixed(3)}</span></div>
              <div className="uppercase text-[10px] tracking-wider">{e.severity}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
