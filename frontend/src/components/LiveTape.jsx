import React, { useEffect, useState } from "react";
import { fetchChart } from "../api.js";
import ClickableQuote from "./ClickableQuote.jsx";

/**
 * Rolling N-minute live activity tape per (asset, venue). Polls the chart
 * endpoint every few seconds and renders the last N minutes of:
 *   - last trade price + bid/ask (bid or ask flashes red on the side just hit)
 *   - per-minute buy / sell volume side-by-side
 *   - per-minute trade count
 *
 * Deliberately no math jargon — the user sees price + buy/sell + trades.
 */

function fmtPrice(p) {
  if (!p) return "—";
  if (p >= 1000) return "$" + p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 1)    return "$" + p.toFixed(4);
  return "$" + p.toFixed(6);
}

function fmtQty(q) {
  if (!q) return "0";
  if (q >= 1000) return q.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (q >= 1)    return q.toFixed(3);
  return q.toFixed(6);
}

export default function LiveTape({ asset, venue, nMinutes = 10, pollMs = 5000 }) {
  const [chart, setChart] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const c = await fetchChart(asset, venue, nMinutes);
        if (alive) setChart(c);
      } catch (e) {
        if (alive) setError(String(e));
      }
    }
    tick();
    const t = setInterval(tick, pollMs);
    return () => { alive = false; clearInterval(t); };
  }, [asset, venue, nMinutes, pollMs]);

  if (error) {
    return <div className="text-rose-400 text-xs">Tape error: {error}</div>;
  }
  if (!chart || !chart.data || chart.data.length === 0) {
    return <div className="text-slate-500 text-xs italic">Waiting for tape data…</div>;
  }

  const bars = chart.data.slice(-nMinutes);
  const last = bars[bars.length - 1] || {};
  const lastAggr = last.last_aggressor || "";
  const askCls = lastAggr === "buy"  ? "text-rose-400 font-bold" : "text-slate-100";
  const bidCls = lastAggr === "sell" ? "text-rose-400 font-bold" : "text-slate-100";

  // Determine global maxima for scaling the per-minute bars
  const maxV = Math.max(1e-9, ...bars.map((b) => Math.max(b.buy_volume || 0, b.sell_volume || 0)));
  const maxT = Math.max(1, ...bars.map((b) => b.n_trades || 0));

  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded p-3 mb-3">
      {/* Header — top-of-book */}
      <div className="flex items-baseline justify-between gap-2 mb-2">
        <div>
          <span className="font-mono text-sm font-semibold">{asset}-USD</span>
          <span className="text-slate-400 text-xs ml-2">on {venue}</span>
        </div>
        <div className="font-mono text-sm">
          <span className="text-slate-100">{fmtPrice(last.price)}</span>
          <span className="text-slate-500 text-xs ml-2">last {nMinutes} min · live</span>
        </div>
      </div>

      {/* Click-to-trade bid/ask cells */}
      <div className="mb-3">
        <ClickableQuote
          asset={asset}
          venue={venue}
          bid={last.bid || 0}
          ask={last.ask || 0}
          lastAggressor={lastAggr}
          size="lg"
        />
      </div>

      {/* Per-minute mini tape: each minute is a row with buy/sell stacked bar */}
      <div className="space-y-0.5 font-mono text-[10px]">
        {bars.map((b, i) => {
          const ts = new Date(b.ts * 1000).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" });
          const buy = b.buy_volume || 0;
          const sell = b.sell_volume || 0;
          const total = buy + sell;
          const buyPctOfMax = (buy / maxV) * 100;
          const sellPctOfMax = (sell / maxV) * 100;
          const tradeCount = b.n_trades || 0;
          const tradePctOfMax = (tradeCount / maxT) * 100;
          return (
            <div key={i} className="grid grid-cols-[3em_1fr_1fr_3em_4em] gap-1 items-center">
              <span className="text-slate-500">{ts}</span>
              {/* sell bar grows leftward from the centerline */}
              <div className="flex justify-end">
                <div className="bg-rose-500/70 h-2 rounded-l" style={{ width: `${sellPctOfMax}%` }} />
              </div>
              {/* buy bar grows rightward from the centerline */}
              <div className="flex">
                <div className="bg-emerald-500/70 h-2 rounded-r" style={{ width: `${buyPctOfMax}%` }} />
              </div>
              <span className={total > 0 ? "text-slate-300 text-right" : "text-slate-600 text-right"}>
                {tradeCount > 0 ? `${tradeCount}t` : "—"}
              </span>
              <span className="text-slate-500 text-right">{fmtQty(total)}</span>
            </div>
          );
        })}
      </div>
      <div className="grid grid-cols-[3em_1fr_1fr_3em_4em] gap-1 mt-2 text-[10px] text-slate-500 uppercase tracking-wider">
        <span></span>
        <span className="text-right">sell</span>
        <span>buy</span>
        <span className="text-right">trades</span>
        <span className="text-right">volume</span>
      </div>
    </div>
  );
}
