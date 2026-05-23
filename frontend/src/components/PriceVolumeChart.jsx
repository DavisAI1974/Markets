import React from "react";
import {
  ComposedChart, Line, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

/**
 * Trader-facing price and flow chart. Shows:
 *   1. Price line over the chart window
 *   2. Per-bar buy volume (positive, green) and sell volume (negative, red)
 *      so the side that's pushing is visually obvious
 *   3. Trade count overlay (small dots) so high-activity bars are visible
 *
 * Input: data.data = [{ts, price, bid, ask, buy_volume, sell_volume,
 *                       n_trades, last_aggressor, ...}]
 */
export default function PriceVolumeChart({ data }) {
  if (!data || !data.data || data.data.length === 0) {
    return <div className="text-slate-500 text-sm italic py-8 text-center">No chart data yet.</div>;
  }
  const series = data.data.map((d, i) => ({
    idx: i,
    ts: d.ts,
    price: d.price,
    bid: d.bid || null,
    ask: d.ask || null,
    buy: d.buy_volume || 0,
    sellNeg: -(d.sell_volume || 0),       // negative so it stacks below zero
    n_trades: d.n_trades || 0,
  }));

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">Price</div>
        <ResponsiveContainer width="100%" height={140}>
          <ComposedChart data={series} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
            <XAxis dataKey="idx" hide />
            <YAxis hide domain={["auto", "auto"]} />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
              labelFormatter={() => ""}
              formatter={(v, name) => [v?.toFixed?.(4) ?? v, name]}
            />
            <Line dataKey="price" stroke="#cbd5e1" dot={false} strokeWidth={1.5} isAnimationActive={false} name="price" />
            <Line dataKey="bid"   stroke="#10b981" dot={false} strokeWidth={1}   isAnimationActive={false} name="bid" strokeDasharray="2 4" />
            <Line dataKey="ask"   stroke="#f43f5e" dot={false} strokeWidth={1}   isAnimationActive={false} name="ask" strokeDasharray="2 4" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div>
        <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">
          Buy / Sell volume per minute
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <ComposedChart data={series} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
            <XAxis dataKey="idx" hide />
            <YAxis hide domain={["auto", "auto"]} />
            <ReferenceLine y={0} stroke="#475569" />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
              labelFormatter={() => ""}
              formatter={(v, name) => [Math.abs(v).toFixed?.(3) ?? v, name === "sellNeg" ? "sell" : name]}
            />
            <Bar dataKey="buy"     fill="#10b981" isAnimationActive={false} name="buy" />
            <Bar dataKey="sellNeg" fill="#f43f5e" isAnimationActive={false} name="sell" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <div>
        <div className="text-xs text-slate-400 uppercase tracking-wide mb-1">
          Trades per minute
        </div>
        <ResponsiveContainer width="100%" height={70}>
          <ComposedChart data={series} margin={{ top: 4, right: 8, left: 8, bottom: 0 }}>
            <XAxis dataKey="idx" hide />
            <YAxis hide domain={[0, "auto"]} />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", fontSize: 12 }}
              labelFormatter={() => ""}
              formatter={(v) => [v, "trades"]}
            />
            <Bar dataKey="n_trades" fill="#64748b" isAnimationActive={false} name="trades" />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
