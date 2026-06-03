import React from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine, Legend } from "recharts";

/**
 * StrengthOverTime — rolling OD coupling-strength meters for one source.
 *   mi_slope   : biology-type readout (slope of MI ~ slope*H_a)
 *   chem_frac  : chemistry-type readout (null fraction on the chem residual relation)
 * Reads /api/strength/{asset}/{venue}.
 */
export default function StrengthOverTime({ data }) {
  if (!data) return <div className="text-slate-500 text-xs italic">loading…</div>;
  const pts = data.points || [];
  if (pts.length === 0) {
    return <div className="text-slate-500 text-xs italic">no strength series yet</div>;
  }
  const series = pts.map((p, i) => ({
    idx: i,
    mi_slope: p.mi_slope,
    chem_frac: p.chem_frac,
    mi_r2: p.mi_slope_r2,
  }));

  return (
    <div className="bg-slate-900 rounded p-3 border border-slate-800">
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={series} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
          <XAxis dataKey="idx" hide />
          <YAxis hide domain={["auto", "auto"]} />
          <ReferenceLine y={0} stroke="#334155" strokeDasharray="2 2" />
          <Tooltip
            contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
            labelFormatter={() => ""}
            formatter={(v, n) => [v?.toFixed?.(3) ?? v, n]}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Line dataKey="mi_slope" name="MI slope (bio)" stroke="#34d399" dot={false} strokeWidth={1.5} isAnimationActive={false} />
          <Line dataKey="chem_frac" name="chem residual (chem)" stroke="#f59e0b" dot={false} strokeWidth={1.5} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
      <div className="text-[10px] text-slate-500 mt-1">
        OD-native strength meters over rolling windows. MI-slope = biology-type coupling readout;
        chem residual = chemistry-type. Both are diagnostics, not (yet) net-of-cost signals.
      </div>
    </div>
  );
}
