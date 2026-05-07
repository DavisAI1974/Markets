import React from "react";
import ClickableQuote from "./ClickableQuote.jsx";
import MiniChart from "./MiniChart.jsx";

const REGIME_STYLES = {
  EQUILIBRIUM_TWO_SIDED: { bg: "bg-blue-950/40",   border: "border-blue-700",  chip: "bg-blue-700",   label: "Healthy two-sided",  icon: "⚖️" },
  WHALE_UP:              { bg: "bg-emerald-950/40",border: "border-emerald-700",chip: "bg-emerald-700",label: "Big buyer detected", icon: "🐋" },
  WHALE_DOWN:            { bg: "bg-red-950/40",    border: "border-red-700",   chip: "bg-red-700",    label: "Big seller detected",icon: "🐋" },
  WHALE_NASCENT_UP:      { bg: "bg-emerald-950/25",border: "border-emerald-600",chip: "bg-emerald-600",label: "Buy pressure forming",  icon: "🐋" },
  WHALE_NASCENT_DOWN:    { bg: "bg-rose-950/25",   border: "border-rose-600",  chip: "bg-rose-600",   label: "Sell pressure forming", icon: "🐋" },
  HERD_UP:               { bg: "bg-orange-950/40", border: "border-orange-700",chip: "bg-orange-600", label: "Buying cascade",     icon: "🌊" },
  HERD_DOWN:             { bg: "bg-rose-950/40",   border: "border-rose-700",  chip: "bg-rose-700",   label: "Selling cascade",    icon: "🌊" },
  WASH_PAIRED:           { bg: "bg-yellow-950/40", border: "border-yellow-700",chip: "bg-yellow-700", label: "Wash — skip",        icon: "⚠️" },
  DEPLETED:              { bg: "bg-gray-900/60",   border: "border-gray-600",  chip: "bg-gray-600",   label: "Quiet",              icon: "💤" },
  UNKNOWN:               { bg: "bg-slate-900/60",  border: "border-slate-700", chip: "bg-slate-700",  label: "Unclassified",       icon: "❓" },
};

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

export default function RegimeCard({ status }) {
  const s = REGIME_STYLES[status.regime] || REGIME_STYLES.UNKNOWN;
  const conf = status.adjusted_confidence ?? status.confidence ?? 0;
  const confPct = (conf * 100).toFixed(0);
  const cvm = status.cross_venue_multiplier ?? 1.0;
  const cvmIcon = cvm > 1.0 ? "✓ confirmed" : cvm < 1.0 ? "✗ disagreement" : "—";
  const lastUpdate = status.last_update_utc
    ? new Date(status.last_update_utc * 1000).toLocaleTimeString("en-US", { hour12: false })
    : "—";

  const buy = status.chunk_buy_volume || 0;
  const sell = status.chunk_sell_volume || 0;
  const total = buy + sell;
  const buyPct = total > 0 ? (buy / total) * 100 : 50;
  const nTrades = status.chunk_n_trades || 0;
  const price = status.current_price || 0;
  const bid = status.current_bid || 0;
  const ask = status.current_ask || 0;
  const lastAggr = status.last_aggressor || "";

  return (
    <div className={`rounded-lg border ${s.border} ${s.bg} p-4 mb-3 relative overflow-hidden`}>
      {/* Top row: asset + big regime headline + icon */}
      <div className="flex items-start justify-between gap-2 mb-3">
        <div className="min-w-0">
          <div className="font-mono text-base font-semibold text-slate-100">
            {status.asset}-USD
            <span className="text-slate-400 text-xs ml-2">on {status.venue}</span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-2xl select-none">{s.icon}</span>
            <span className="font-semibold text-base text-slate-100">{s.label}</span>
          </div>
        </div>
        <div className="text-right">
          <div className="font-mono text-lg text-slate-100">{fmtPrice(price)}</div>
          <div className="text-[10px] text-slate-500 uppercase tracking-wide">last price</div>
        </div>
      </div>

      {/* Confidence + cross-venue chip row */}
      <div className="flex items-center gap-2 mb-3 text-xs">
        <span className={`px-2 py-0.5 rounded text-white text-xs font-semibold ${s.chip}`}>
          {confPct}% conf
        </span>
        <span className={`text-xs ${cvm > 1.0 ? "text-emerald-400" : cvm < 1.0 ? "text-yellow-500" : "text-slate-500"}`}>
          {cvmIcon}
        </span>
        <span className="text-slate-500 ml-auto">{lastUpdate} UTC</span>
      </div>

      {/* Click-to-trade bid/ask cells */}
      <ClickableQuote
        asset={status.asset}
        venue={status.venue}
        bid={bid}
        ask={ask}
        lastAggressor={lastAggr}
      />

      {/* Buy/sell stacked bar — shows the aggressor split for this chunk */}
      {total > 0 && (
        <div className="mt-3">
          <div className="flex justify-between text-[10px] text-slate-400 uppercase tracking-wide mb-1">
            <span>Buy / Sell · this chunk</span>
            <span>{nTrades} trade{nTrades === 1 ? "" : "s"}</span>
          </div>
          <div className="flex h-2.5 rounded overflow-hidden bg-slate-800">
            <div className="bg-gradient-to-r from-emerald-600 to-emerald-400" style={{ width: `${buyPct}%` }} />
            <div className="bg-gradient-to-r from-rose-400 to-rose-600"        style={{ width: `${100 - buyPct}%` }} />
          </div>
          <div className="flex justify-between text-[11px] mt-1 font-mono">
            <span className="text-emerald-400">{buyPct.toFixed(0)}% buy · {fmtQty(buy)} {status.asset}</span>
            <span className="text-rose-400">{(100 - buyPct).toFixed(0)}% sell · {fmtQty(sell)} {status.asset}</span>
          </div>
        </div>
      )}

      {/* Mini chart — last 30m price + buy/sell volume */}
      <div className="mt-3">
        <div className="text-[10px] text-slate-500 uppercase tracking-wide mb-1">
          Last 30 min · price + flow
        </div>
        <MiniChart asset={status.asset} venue={status.venue} nMinutes={30} height={32} />
      </div>
    </div>
  );
}
