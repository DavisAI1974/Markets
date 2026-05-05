import React from "react";
import ClickableQuote from "./ClickableQuote.jsx";

const REGIME_STYLES = {
  EQUILIBRIUM_TWO_SIDED: { bg: "bg-blue-950/40",   border: "border-blue-700",  chip: "bg-blue-700",   label: "Healthy two-sided" },
  WHALE_UP:              { bg: "bg-green-950/40",  border: "border-green-700", chip: "bg-green-700",  label: "Big buyer detected" },
  WHALE_DOWN:            { bg: "bg-red-950/40",    border: "border-red-700",   chip: "bg-red-700",    label: "Big seller detected" },
  HERD_UP:               { bg: "bg-orange-950/40", border: "border-orange-700",chip: "bg-orange-600", label: "Buying cascade" },
  HERD_DOWN:             { bg: "bg-rose-950/40",   border: "border-rose-700",  chip: "bg-rose-700",   label: "Selling cascade" },
  WASH_PAIRED:           { bg: "bg-yellow-950/40", border: "border-yellow-700",chip: "bg-yellow-700", label: "Wash pattern — skip" },
  DEPLETED:              { bg: "bg-gray-900/60",   border: "border-gray-600",  chip: "bg-gray-600",   label: "Quiet" },
  UNKNOWN:               { bg: "bg-slate-900/60",  border: "border-slate-700", chip: "bg-slate-700",  label: "Unclassified" },
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
  // Tape-side flash: if the last trade was an aggressor-buy (lifted ask),
  // the ask price is what just got paid → flash red. If aggressor-sell
  // (hit bid), the bid is what was paid → flash red. Other side stays
  // default text color.
  const lastAggr = status.last_aggressor || "";
  const askCls = lastAggr === "buy"  ? "text-rose-400 font-bold" : "text-slate-100";
  const bidCls = lastAggr === "sell" ? "text-rose-400 font-bold" : "text-slate-100";

  return (
    <div className={`rounded-lg border ${s.border} ${s.bg} p-4 mb-3`}>
      <div className="flex items-center justify-between gap-2">
        <div className="font-mono text-base font-semibold">
          {status.asset}-USD <span className="text-slate-400 text-sm">on {status.venue}</span>
        </div>
        <span className={`px-2 py-1 rounded text-xs font-semibold ${s.chip} whitespace-nowrap`}>{s.label}</span>
      </div>

      {/* Last price + confidence on top, then click-to-trade bid/ask cells.
          Each cell is independently clickable; opens an order ticket
          pre-filled with side + price. */}
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <Metric label="Last price" value={fmtPrice(price)} mono />
        <Metric label="Confidence" value={`${confPct}%`} mono />
      </div>
      <div className="mt-2">
        <ClickableQuote
          asset={status.asset}
          venue={status.venue}
          bid={bid}
          ask={ask}
          lastAggressor={lastAggr}
        />
      </div>

      {/* Buy/sell stacked bar — visually obvious aggressor split */}
      {total > 0 && (
        <div className="mt-3">
          <div className="flex justify-between text-[10px] text-slate-400 uppercase tracking-wide mb-1">
            <span>Buy / Sell  ·  this chunk</span>
            <span>{nTrades} trade{nTrades === 1 ? "" : "s"}</span>
          </div>
          <div className="flex h-2.5 rounded overflow-hidden bg-slate-800">
            <div className="bg-emerald-500" style={{ width: `${buyPct}%` }} />
            <div className="bg-rose-500"    style={{ width: `${100 - buyPct}%` }} />
          </div>
          <div className="flex justify-between text-[11px] mt-1 font-mono">
            <span className="text-emerald-400">{buyPct.toFixed(0)}% buy · {fmtQty(buy)} {status.asset}</span>
            <span className="text-rose-400">{(100 - buyPct).toFixed(0)}% sell · {fmtQty(sell)} {status.asset}</span>
          </div>
        </div>
      )}

      <div className="mt-2 flex items-center justify-between text-xs text-slate-400">
        <span>cross-venue: {cvmIcon}</span>
        <span>{lastUpdate} UTC</span>
      </div>
    </div>
  );
}

function Metric({ label, value, mono }) {
  return (
    <div className="bg-slate-950/60 rounded px-2 py-1">
      <div className="text-slate-500 text-[10px] uppercase tracking-wide">{label}</div>
      <div className={`text-sm ${mono ? "font-mono" : ""}`}>{value}</div>
    </div>
  );
}
