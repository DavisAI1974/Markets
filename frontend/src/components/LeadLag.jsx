import React from "react";

/**
 * LeadLag — who-moves-first across venues for an asset. Reads /api/leadlag/{asset}.
 * Positive lag means `a` leads `b`; the detector reports the leader and z vs a
 * time-slide null (the S19 raw cross-cov-over-lag tool).
 */
export default function LeadLag({ asset, data }) {
  if (!data) return <div className="text-slate-500 text-xs italic">loading…</div>;
  const cells = data.cells || [];
  if (cells.length === 0) {
    return <div className="text-slate-500 text-xs italic">no lead-lag for {asset} yet</div>;
  }
  return (
    <div className="bg-slate-900 rounded p-3 border border-slate-800 space-y-2">
      {cells.map((c, i) => {
        const sync = c.leader === "synchronous";
        const sig = c.z >= 3;
        return (
          <div key={i} className="flex items-center justify-between text-xs font-mono border-b border-slate-800/60 last:border-0 pb-2 last:pb-0">
            <div className="text-slate-300">
              {c.a} <span className="text-slate-600">vs</span> {c.b}
            </div>
            <div className="flex items-center gap-3">
              <span className={sync ? "text-slate-400" : "text-emerald-400"}>
                {sync ? "synchronous" : `${c.leader.split("/")[1]} leads ${Math.abs(c.lag_seconds)}s`}
              </span>
              <span className="text-slate-500">cc={c.cc.toFixed(2)}</span>
              <span className={`px-1.5 py-0.5 rounded ${sig ? "bg-emerald-900/60 text-emerald-200" : "bg-slate-800 text-slate-500"}`}
                    title="z vs time-slide null (>=3 is significant)">
                z={c.z.toFixed(0)}
              </span>
            </div>
          </div>
        );
      })}
      <div className="text-[10px] text-slate-500 pt-1">
        At minute cadence venues are near-synchronous; a +/-1-bar lead is the resolution floor (sub-second leads need tick data).
      </div>
    </div>
  );
}
