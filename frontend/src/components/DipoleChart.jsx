import React from "react";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

export default function DipoleChart({ data }) {
  if (!data || !data.data || data.data.length === 0) {
    return <div className="text-slate-500 text-sm italic py-8 text-center">No chart data yet.</div>;
  }
  const series = data.data.map((d, i) => ({
    idx: i,
    ts: d.ts,
    price: d.price,
    dipole: d.dipole,
  }));

  return (
    <div className="space-y-3">
      <div>
        <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">Price</div>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={series} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
            <XAxis dataKey="idx" hide />
            <YAxis hide domain={["auto", "auto"]} />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
              labelFormatter={() => ""}
              formatter={(v) => v?.toFixed?.(2) ?? v}
            />
            <Line dataKey="price" stroke="#cbd5e1" dot={false} strokeWidth={1.5} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div>
        <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">Dipole (per minute)</div>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={series} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
            <XAxis dataKey="idx" hide />
            <YAxis hide domain={[-1, 1]} />
            <ReferenceLine y={0} stroke="#475569" strokeDasharray="2 2" />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
              labelFormatter={() => ""}
              formatter={(v) => v?.toFixed?.(3) ?? v}
            />
            <Line dataKey="dipole" stroke="#3b82f6" dot={false} strokeWidth={1.5} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
