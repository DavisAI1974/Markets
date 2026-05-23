import React, { useEffect, useState } from "react";
import { fetchChart } from "../api.js";
import ClickableQuote from "./ClickableQuote.jsx";
import { getMarketReadLabel, getMarketStructureCopy } from "../marketReadCopy.js";

// Live tape: pair + current read · big Bid/Ask cells ·
// spread / last-hit meta · per-minute table (Min · Buy vol · Sell vol · Trd
// · Price) · read-colored flow summary banner at bottom.
// Polls /api/chart at pollMs interval.

const READ_BANNER = {
  WHALE_UP:              { txt: "#4ade80", bg: "rgba(34,197,94,0.08)",  border: "#22c55e" },
  WHALE_DOWN:            { txt: "#f87171", bg: "rgba(239,68,68,0.08)",  border: "#ef4444" },
  WHALE_NASCENT_UP:      { txt: "#6ee7b7", bg: "rgba(16,185,129,0.08)", border: "#10b981" },
  WHALE_NASCENT_DOWN:    { txt: "#fda4af", bg: "rgba(244,63,94,0.08)",  border: "#f43f5e" },
  HERD_UP:               { txt: "#fb923c", bg: "rgba(249,115,22,0.08)", border: "#f97316" },
  HERD_DOWN:             { txt: "#f87171", bg: "rgba(185,28,28,0.10)",  border: "#b91c1c" },
  CROSS_VENUE_WHALE_HERD_UP:   { txt: "#6ee7b7", bg: "rgba(16,185,129,0.10)", border: "#10b981" },
  CROSS_VENUE_HERD_WHALE_UP:   { txt: "#6ee7b7", bg: "rgba(16,185,129,0.10)", border: "#10b981" },
  CROSS_VENUE_WHALE_HERD_DOWN: { txt: "#fda4af", bg: "rgba(244,63,94,0.10)",  border: "#f43f5e" },
  CROSS_VENUE_HERD_WHALE_DOWN: { txt: "#fda4af", bg: "rgba(244,63,94,0.10)",  border: "#f43f5e" },
  EQUILIBRIUM_TWO_SIDED: { txt: "#60a5fa", bg: "rgba(59,130,246,0.08)", border: "#3b82f6" },
  WASH_PAIRED:           { txt: "#facc15", bg: "rgba(234,179,8,0.08)",  border: "#eab308" },
  DEPLETED:              { txt: "#9ca3af", bg: "rgba(156,163,175,0.06)",border: "#9ca3af" },
  UNKNOWN:               { txt: "#94a3b8", bg: "rgba(100,116,139,0.06)",border: "#64748b" },
};
const READ_BADGE_COLOR = {
  WHALE_UP: "#4ade80", WHALE_DOWN: "#f87171",
  WHALE_NASCENT_UP: "#6ee7b7", WHALE_NASCENT_DOWN: "#fda4af",
  HERD_UP: "#fb923c", HERD_DOWN: "#f87171",
  CROSS_VENUE_WHALE_HERD_UP: "#6ee7b7", CROSS_VENUE_HERD_WHALE_UP: "#6ee7b7",
  CROSS_VENUE_WHALE_HERD_DOWN: "#fda4af", CROSS_VENUE_HERD_WHALE_DOWN: "#fda4af",
  EQUILIBRIUM_TWO_SIDED: "#60a5fa", WASH_PAIRED: "#facc15",
  DEPLETED: "#9ca3af", UNKNOWN: "#94a3b8",
};

function fmtPrice(p) {
  if (!p) return "—";
  if (p >= 1000) return p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 1)    return p.toFixed(4);
  return p.toFixed(6);
}

function fmtQty(q) {
  if (q == null) return "—";
  if (q >= 1000) return q.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (q >= 1)    return q.toFixed(3);
  return q.toFixed(6);
}

function fmtMinute(ts) {
  return new Date(ts * 1000).toLocaleTimeString("en-US", {
    hour12: false, hour: "2-digit", minute: "2-digit",
  });
}

function fmtSpread(bid, ask) {
  if (!bid || !ask) return "—";
  const d = ask - bid;
  if (d <= 0) return "—";
  const bp = (d / ((bid + ask) / 2)) * 10000;
  // Tight format match: "0.20 · 1.6 bp"
  const dollarPart = d >= 1 ? d.toFixed(2) : d.toFixed(4);
  const bpPart = bp < 0.1 ? bp.toFixed(2) : bp.toFixed(1);
  return `${dollarPart} · ${bpPart} bp`;
}

export default function LiveTape({ asset, venue, regime = null, status = null, nMinutes = 6, pollMs = 5000 }) {
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

  // Newest at bottom of the slice; reverse for table display (newest first)
  const barsAsc = chart.data.slice(-nMinutes);
  const bars = [...barsAsc].reverse();
  const last = barsAsc[barsAsc.length - 1] || {};
  const lastAggr = last.last_aggressor || "";

  const readLabel = regime ? getMarketReadLabel(regime) : null;
  const structureCopy = regime ? getMarketStructureCopy(regime) : null;
  const readColor = regime ? (READ_BADGE_COLOR[regime] || "#94a3b8") : null;
  const banner = regime ? (READ_BANNER[regime] || READ_BANNER.UNKNOWN) : READ_BANNER.UNKNOWN;
  const pressureLabel = status?.pressure_watch_state === "internal"
    ? ""
    : (status?.pressure_watch_label || "");
  const pressureReason = (status?.pressure_watch_reasons || [])[0] || "";

  // Scale bars to the widest volume in the visible window
  const maxV = Math.max(1e-9, ...barsAsc.map((b) => Math.max(b.buy_volume || 0, b.sell_volume || 0)));

  // Flow summary: count buy-dominant minutes, total volume + taker% on latest
  const buyDominantMin = barsAsc.filter((b) => (b.buy_volume || 0) > (b.sell_volume || 0)).length;
  const lastBuy  = last.buy_volume || 0;
  const lastSell = last.sell_volume || 0;
  const lastTotal = lastBuy + lastSell;
  const takerBuyPct = lastTotal > 0 ? (lastBuy / lastTotal) * 100 : 0;

  return (
    <div className="text-slate-200">
      {/* Header — pair + current read */}
      <div className="flex justify-between items-center text-[11px] text-slate-400 pb-2">
        <span>
          <span className="text-slate-100 font-semibold text-[13px]">
            {asset}-USD
          </span>
          <span className="text-slate-400 font-normal text-[12px] ml-2">on {venue}</span>
        </span>
        {readLabel && (
          <span>
            current read: <span className="font-semibold" style={{ color: readColor }}>{readLabel}</span>
          </span>
        )}
      </div>

      {/* Big Bid / Ask cells with last-minute volume per side */}
      <ClickableQuote
        asset={asset}
        venue={venue}
        bid={last.bid || 0}
        ask={last.ask || 0}
        lastAggressor={lastAggr}
        bidVolume={lastSell}
        askVolume={lastBuy}
        volumeLabel="1m vol"
        tradeOption={status}
      />

      {/* Spread + last-hit meta */}
      <div className="flex justify-between text-[11px] text-slate-400 pt-2 pb-1.5 px-1">
        <span>spread {fmtSpread(last.bid, last.ask)}</span>
        <span>
          last hit: {lastAggr === "buy" ? (
            <span className="text-rose-400">ask</span>
          ) : lastAggr === "sell" ? (
            <span className="text-rose-400">bid</span>
          ) : (
            <span className="text-slate-500">—</span>
          )}
        </span>
      </div>

      {/* Per-minute table */}
      <table className="w-full border-collapse font-mono text-[11px] mt-1">
        <thead>
          <tr>
            <th className="text-left text-[9px] uppercase tracking-wider text-slate-500 font-semibold py-1.5 pr-1 border-b border-slate-800">Min</th>
            <th className="text-left text-[9px] uppercase tracking-wider text-slate-500 font-semibold py-1.5 px-1 border-b border-slate-800">Buy vol</th>
            <th className="text-left text-[9px] uppercase tracking-wider text-slate-500 font-semibold py-1.5 px-1 border-b border-slate-800">Sell vol</th>
            <th className="text-center text-[9px] uppercase tracking-wider text-slate-500 font-semibold py-1.5 px-1 border-b border-slate-800">Trd</th>
            <th className="text-right text-[9px] uppercase tracking-wider text-slate-500 font-semibold py-1.5 pl-1 border-b border-slate-800">Price</th>
          </tr>
        </thead>
        <tbody>
          {bars.map((b, i) => {
            const buy = b.buy_volume || 0;
            const sell = b.sell_volume || 0;
            const buyW = (buy / maxV) * 100;
            const sellW = (sell / maxV) * 100;
            const isLatest = i === 0;
            return (
              <tr key={b.ts} className={`border-b border-slate-900 ${isLatest ? "bg-emerald-500/[0.05]" : ""}`}>
                <td className="text-slate-500 py-1.5 pr-1">{fmtMinute(b.ts)}</td>
                <td className="text-slate-200 py-1.5 px-1">
                  <div className="flex items-center gap-1.5">
                    <div className="h-[7px] rounded-[1px] flex-shrink-0 bg-green-700" style={{ width: `${buyW * 0.5}px`, minWidth: buy > 0 ? "1px" : "0" }} />
                    <span className="min-w-[28px]">{fmtQty(buy)}</span>
                  </div>
                </td>
                <td className="text-slate-200 py-1.5 px-1">
                  <div className="flex items-center gap-1.5">
                    <div className="h-[7px] rounded-[1px] flex-shrink-0 bg-red-700" style={{ width: `${sellW * 0.5}px`, minWidth: sell > 0 ? "1px" : "0" }} />
                    <span className="min-w-[28px]">{fmtQty(sell)}</span>
                  </div>
                </td>
                <td className="text-slate-400 py-1.5 px-1 text-center">{b.n_trades || 0}</td>
                <td className="text-amber-400 py-1.5 pl-1 text-right">{fmtPrice(b.price)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Flow summary banner — regime-tinted */}
      <div
        className="mt-2.5 px-2.5 py-2 text-[11px] text-slate-300 leading-snug rounded-r"
        style={{
          background: banner.bg,
          borderLeft: `2px solid ${banner.border}`,
          borderTopLeftRadius: 0,
          borderBottomLeftRadius: 0,
        }}
      >
        <span className="font-semibold" style={{ color: banner.txt }}>
          {buyDominantMin > nMinutes / 2 ? "Buy" : buyDominantMin < nMinutes / 2 ? "Sell" : "Mixed"} flow {buyDominantMin > nMinutes / 2 || buyDominantMin < nMinutes / 2 ? "dominant" : ""} {buyDominantMin}/{nMinutes} min.
        </span>
        {" "}
        1m vol {fmtQty(lastTotal)} {asset} · taker buy {takerBuyPct.toFixed(0)}%.
        {readLabel && (
          <div className="mt-1 text-slate-300">
            {structureCopy}
          </div>
        )}
        {pressureLabel && (
          <div className="mt-1 text-amber-200">
            {pressureLabel}{pressureReason ? `: ${pressureReason}` : ""}
          </div>
        )}
      </div>
    </div>
  );
}
