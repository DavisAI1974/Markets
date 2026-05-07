import React, { useEffect, useState } from "react";
import { fetchSignalDetail } from "../api.js";
import PriceVolumeChart from "./PriceVolumeChart.jsx";

/**
 * Reusable signal-detail body. Used by:
 *   - SignalDetail page route (full-screen, with back-link)
 *   - SignalDetailSheet bottom-sheet overlay (mobile-native feel)
 *
 * Owns its own data fetch from /api/signal/{id}. Renders a loading
 * placeholder, an error state, or the detail content.
 */

const REGIME_HEADLINES = {
  WHALE_UP:   "Big buyer detected",
  WHALE_DOWN: "Big seller detected",
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

export default function SignalDetailBody({ id }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setData(null);
    setError(null);
    fetchSignalDetail(id)
      .then((d) => !cancelled && setData(d))
      .catch((e) => !cancelled && setError(e.message));
    return () => { cancelled = true; };
  }, [id]);

  if (error) return <div className="text-red-400 text-sm p-2">Error: {error}</div>;
  if (!data) return <div className="text-slate-500 text-sm p-2">Loading…</div>;

  const sig = data.signal;
  const time = new Date(sig.timestamp_utc * 1000).toLocaleString();
  const conf = sig.adjusted_confidence ?? sig.confidence ?? 0;
  const cvm = sig.cross_venue_multiplier ?? 1.0;
  const cascade = sig.cascade_event || "";
  const headline = sig.event_label
    || REGIME_HEADLINES[sig.regime]
    || sig.regime.replace(/_/g, " ");

  const buy = sig.chunk_buy_volume || 0;
  const sell = sig.chunk_sell_volume || 0;
  const total = buy + sell;
  const buyPct = total > 0 ? (buy / total) * 100 : 50;
  const nTrades = sig.chunk_n_trades || 0;
  const price = sig.current_price || 0;
  const bid = sig.current_bid || 0;
  const ask = sig.current_ask || 0;
  const lastAggr = sig.last_aggressor || "";
  const askCls = lastAggr === "buy"  ? "text-rose-400 font-bold" : "text-slate-100";
  const bidCls = lastAggr === "sell" ? "text-rose-400 font-bold" : "text-slate-100";

  return (
    <div className="space-y-4">
      <div className="bg-slate-900 rounded-lg p-4 border border-slate-800">
        {cascade && (
          <div className="mb-2 text-[11px] uppercase tracking-wider font-bold text-amber-300">
            {cascade.startsWith("CROSS_VENUE") ? "🌊🌊 cross-venue cascade" : "🌊 whale → herd cascade"}
          </div>
        )}
        {sig.drift_status && (
          <div className="mb-2 inline-block text-[10px] uppercase tracking-wider font-bold text-amber-300 border border-amber-700/60 bg-amber-950/40 rounded px-1.5 py-0.5">
            ⚠ {sig.drift_status === "unstable" ? "cell unstable"
                : sig.drift_status === "recently_flipped" ? "direction recently flipped"
                : sig.drift_status === "decaying" ? "edge decaying"
                : "drift detected"}
          </div>
        )}

        <div className="flex items-start justify-between gap-2 mb-2">
          <div>
            <div className="text-lg font-semibold">{headline}</div>
            <div className="text-sm text-slate-400">{sig.asset}-USD · {sig.venue}</div>
          </div>
          <div className="text-right text-xs text-slate-500 font-mono">
            {time}
            <div className="mt-1">conf {(conf * 100).toFixed(0)}%</div>
          </div>
        </div>

        {/* Quote row — bid or ask flashes red on the side just hit */}
        <div className="grid grid-cols-3 gap-2 mt-3 text-sm">
          <Metric label="Price" value={fmtPrice(price)} />
          <div className="bg-slate-950 rounded px-2 py-1.5">
            <div className="text-slate-500 text-[10px] uppercase tracking-wide">Bid / Ask</div>
            <div className="font-mono text-sm mt-0.5">
              {bid ? <span className={bidCls}>{fmtPrice(bid)}</span> : <span>—</span>}
              <span className="text-slate-500"> / </span>
              {ask ? <span className={askCls}>{fmtPrice(ask)}</span> : <span>—</span>}
            </div>
          </div>
          <Metric
            label="Cross-venue"
            value={cvm > 1.0 ? "✓ confirmed" : cvm < 1.0 ? "✗ single-venue" : "—"}
          />
        </div>

        {/* Buy/sell stacked bar */}
        {total > 0 && (
          <div className="mt-4">
            <div className="flex justify-between text-[10px] text-slate-400 uppercase tracking-wide mb-1">
              <span>Buy / Sell volume on this chunk</span>
              <span>{nTrades} trade{nTrades === 1 ? "" : "s"}</span>
            </div>
            <div className="flex h-3 rounded overflow-hidden bg-slate-800">
              <div className="bg-emerald-500" style={{ width: `${buyPct}%` }} />
              <div className="bg-rose-500"    style={{ width: `${100 - buyPct}%` }} />
            </div>
            <div className="flex justify-between text-[11px] mt-1 font-mono">
              <span className="text-emerald-400">{buyPct.toFixed(0)}% buy · {fmtQty(buy)} {sig.asset}</span>
              <span className="text-rose-400">{(100 - buyPct).toFixed(0)}% sell · {fmtQty(sell)} {sig.asset}</span>
            </div>
          </div>
        )}

        <div className="mt-4 p-3 bg-slate-950 rounded text-sm">
          <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Playbook</div>
          {sig.playbook}
        </div>

        {sig.outcome_status === "resolved" && (
          <div className={`mt-3 text-sm font-mono ${sig.outcome_realized_bps >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            outcome: {sig.outcome_realized_bps >= 0 ? "+" : ""}{sig.outcome_realized_bps.toFixed(1)} bps
          </div>
        )}
      </div>

      <div className="bg-slate-900 rounded-lg p-4 border border-slate-800">
        <PriceVolumeChart data={data.chart} />
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="bg-slate-950 rounded px-2 py-1.5">
      <div className="text-slate-500 text-[10px] uppercase tracking-wide">{label}</div>
      <div className="font-mono text-sm mt-0.5">{value ?? "—"}</div>
    </div>
  );
}
