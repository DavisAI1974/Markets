import React, { useEffect, useState } from "react";
import { useStore } from "../store.js";

const REGIME_COLORS = {
  WHALE_UP:   "border-l-green-500",
  WHALE_DOWN: "border-l-red-500",
  WHALE_NASCENT_UP:   "border-l-emerald-400",
  WHALE_NASCENT_DOWN: "border-l-rose-400",
  HERD_UP:    "border-l-orange-500",
  HERD_DOWN:  "border-l-rose-700",
  WASH_PAIRED:"border-l-yellow-500",
  EQUILIBRIUM_TWO_SIDED: "border-l-blue-500",
  DEPLETED:   "border-l-gray-500",
  UNKNOWN:    "border-l-slate-500",
  CROSS_VENUE_WHALE_HERD_UP:   "border-l-emerald-400",
  CROSS_VENUE_HERD_WHALE_UP:   "border-l-emerald-400",
  CROSS_VENUE_WHALE_HERD_DOWN: "border-l-rose-400",
  CROSS_VENUE_HERD_WHALE_DOWN: "border-l-rose-400",
};

const REGIME_HEADLINES = {
  WHALE_UP:   "Big buyer detected",
  WHALE_DOWN: "Big seller detected",
  WHALE_NASCENT_UP:   "Buy pressure forming",
  WHALE_NASCENT_DOWN: "Sell pressure forming",
  HERD_UP:    "Buying cascade",
  HERD_DOWN:  "Selling cascade",
  WASH_PAIRED:"Wash pattern — skip",
  EQUILIBRIUM_TWO_SIDED: "Healthy two-sided",
  DEPLETED:   "Market quiet",
  UNKNOWN:    "Unclassified",
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

export default function SignalCard({ sig, isFresh = false }) {
  const cls = REGIME_COLORS[sig.regime] || "border-l-slate-500";
  const time = new Date(sig.timestamp_utc * 1000).toLocaleTimeString("en-US", { hour12: false });
  const conf = sig.adjusted_confidence ?? sig.confidence ?? 0;
  const cvm = sig.cross_venue_multiplier ?? 1.0;
  const cascade = sig.cascade_event || "";
  const headline = sig.event_label
    || REGIME_HEADLINES[sig.regime]
    || sig.regime.replace(/_/g, " ");

  // Animation hook: cards rendered for the first time after their parent
  // listens to a new SSE signal use the slide-in + cascade-pulse classes.
  const [animClass, setAnimClass] = useState(
    isFresh ? (cascade ? "animate-signal-in animate-cascade-pulse" : "animate-signal-in") : ""
  );
  useEffect(() => {
    if (!isFresh) return;
    // Haptic on cascade arrivals (Android Chrome supports navigator.vibrate;
    // iOS Safari ignores). Guarded — single short pulse for cascades.
    if (cascade && typeof navigator !== "undefined" && navigator.vibrate) {
      try { navigator.vibrate([60, 40, 60]); } catch {}
    } else if (typeof navigator !== "undefined" && navigator.vibrate) {
      try { navigator.vibrate(40); } catch {}
    }
    const t = setTimeout(() => setAnimClass(""), 3500);
    return () => clearTimeout(t);
  }, [isFresh, cascade]);

  const buy = sig.chunk_buy_volume || 0;
  const sell = sig.chunk_sell_volume || 0;
  const total = buy + sell;
  const buyPct = total > 0 ? (buy / total) * 100 : 50;
  const nTrades = sig.chunk_n_trades || 0;
  const price = sig.current_price || 0;
  const bid = sig.current_bid || 0;
  const ask = sig.current_ask || 0;
  const lastAggr = sig.last_aggressor || "";
  const askCls = lastAggr === "buy"  ? "text-rose-400 font-bold" : "text-slate-300";
  const bidCls = lastAggr === "sell" ? "text-rose-400 font-bold" : "text-slate-300";

  const cascadeRibbonCls = cascade
    ? "border-t-4 border-t-amber-400 bg-gradient-to-b from-amber-950/40 to-slate-900/70"
    : "bg-slate-900/70";

  const openSheet = useStore((s) => s.openSignalSheet);
  return (
    <button
      type="button"
      onClick={() => openSheet(sig.signal_id)}
      className={`block w-full text-left ${cascadeRibbonCls} border-l-4 ${cls} rounded-r p-3 mb-2 hover:bg-slate-900
                    transition relative overflow-hidden ${animClass}`}
    >
      {/* Cascade watermark + ribbon if applicable */}
      {cascade && (
        <>
          <div className="absolute top-1 right-2 text-3xl opacity-15 select-none pointer-events-none">
            {cascade.startsWith("CROSS_VENUE") ? "🌊🌊" : "🌊"}
          </div>
          <div className="mb-2 text-[10px] uppercase tracking-wider font-bold text-amber-300">
            {cascade.startsWith("CROSS_VENUE") ? "🌊🌊 cross-venue cascade" : "🌊 whale → herd cascade"}
          </div>
        </>
      )}

      {/* Drift badge — surfaces when the cell's edge is in flux. Plain
          language so users know to read this signal with skepticism. */}
      {sig.drift_status && (
        <div className="mb-2 inline-block text-[10px] uppercase tracking-wider font-bold text-amber-300 border border-amber-700/60 bg-amber-950/40 rounded px-1.5 py-0.5">
          ⚠ {sig.drift_status === "unstable" ? "cell unstable"
              : sig.drift_status === "recently_flipped" ? "direction recently flipped"
              : sig.drift_status === "decaying" ? "edge decaying"
              : "drift detected"}
        </div>
      )}

      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-semibold text-sm">
            {headline}
            <span className="text-slate-400 ml-2 text-xs">{sig.asset}-USD on {sig.venue}</span>
          </div>
          <div className="text-xs mt-1 font-mono">
            <span className="text-slate-300">{fmtPrice(price)}</span>
            {(bid || ask) && (
              <span className="text-slate-500">
                {" · bid "}<span className={bidCls}>{fmtPrice(bid)}</span>
                {" / ask "}<span className={askCls}>{fmtPrice(ask)}</span>
              </span>
            )}
            <span className="text-slate-500"> · conf {(conf * 100).toFixed(0)}%</span>
            {cvm > 1.0 && <span className="text-emerald-400 ml-1">✓ cross-venue</span>}
            {cvm < 1.0 && <span className="text-yellow-500 ml-1">✗ single-venue</span>}
          </div>
        </div>
        <span className="text-xs text-slate-500 font-mono whitespace-nowrap">{time}</span>
      </div>

      {/* Buy/sell stacked bar */}
      {total > 0 && (
        <div className="mt-2">
          <div className="flex h-1.5 rounded overflow-hidden bg-slate-800">
            <div className="bg-emerald-500" style={{ width: `${buyPct}%` }} />
            <div className="bg-rose-500"    style={{ width: `${100 - buyPct}%` }} />
          </div>
          <div className="flex justify-between text-[10px] mt-1 font-mono text-slate-400">
            <span>{buyPct.toFixed(0)}% buy · {fmtQty(buy)}</span>
            <span>{(100 - buyPct).toFixed(0)}% sell · {fmtQty(sell)} · {nTrades} trades</span>
          </div>
        </div>
      )}

      <div className="text-xs text-slate-400 mt-2 line-clamp-2">{sig.playbook}</div>

      {sig.outcome_status === "resolved" && (
        <div className={`mt-2 text-xs font-mono ${sig.outcome_realized_bps >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
          outcome: {sig.outcome_realized_bps >= 0 ? "+" : ""}{sig.outcome_realized_bps.toFixed(1)} bps
        </div>
      )}
      {sig.outcome_status === "pending" && (
        <div className="mt-2 text-xs text-slate-500 italic">outcome: pending (resolves ~30 min after entry)</div>
      )}
    </button>
  );
}
