import React from "react";
import { getMarketReadLabel, getMarketStructureCopy, getReadQualityLabel } from "../marketReadCopy.js";

const READ_STYLES = {
  EQUILIBRIUM_TWO_SIDED: { bg: "bg-blue-950/40", border: "border-blue-700", chip: "bg-blue-700" },
  WHALE_UP: { bg: "bg-green-950/40", border: "border-green-700", chip: "bg-green-700" },
  WHALE_DOWN: { bg: "bg-red-950/40", border: "border-red-700", chip: "bg-red-700" },
  WHALE_NASCENT_UP: { bg: "bg-emerald-950/30", border: "border-emerald-600", chip: "bg-emerald-600" },
  WHALE_NASCENT_DOWN: { bg: "bg-rose-950/30", border: "border-rose-600", chip: "bg-rose-600" },
  HERD_UP: { bg: "bg-orange-950/40", border: "border-orange-700", chip: "bg-orange-600" },
  HERD_DOWN: { bg: "bg-rose-950/40", border: "border-rose-700", chip: "bg-rose-700" },
  CROSS_VENUE_WHALE_HERD_UP: { bg: "bg-emerald-950/40", border: "border-emerald-500", chip: "bg-emerald-600" },
  CROSS_VENUE_HERD_WHALE_UP: { bg: "bg-emerald-950/40", border: "border-emerald-500", chip: "bg-emerald-600" },
  CROSS_VENUE_WHALE_HERD_DOWN: { bg: "bg-rose-950/40", border: "border-rose-500", chip: "bg-rose-600" },
  CROSS_VENUE_HERD_WHALE_DOWN: { bg: "bg-rose-950/40", border: "border-rose-500", chip: "bg-rose-600" },
  WASH_PAIRED: { bg: "bg-yellow-950/40", border: "border-yellow-700", chip: "bg-yellow-700" },
  WASH_HAWKES: { bg: "bg-yellow-950/40", border: "border-yellow-700", chip: "bg-yellow-700" },
  DEPLETED: { bg: "bg-gray-900/60", border: "border-gray-600", chip: "bg-gray-600" },
  UNKNOWN: { bg: "bg-slate-900/60", border: "border-slate-700", chip: "bg-slate-700" },
};

function fmtRealVol(rv) {
  if (rv == null || isNaN(rv)) return "-";
  return (rv * 10000).toFixed(1) + " bp";
}

function fmtQty(q) {
  if (q == null || isNaN(q)) return "0";
  if (q >= 1000) return q.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (q >= 1) return q.toFixed(3);
  return q.toFixed(6);
}

function getFlow(status) {
  const buy = status.chunk_buy_volume || 0;
  const sell = status.chunk_sell_volume || 0;
  const total = buy + sell;
  if (total <= 0) {
    return { label: "waiting", detail: "flow building" };
  }

  const buyPct = (buy / total) * 100;
  const sellPct = 100 - buyPct;
  const leader = buyPct >= sellPct ? "buy" : "sell";
  const leaderPct = Math.max(buyPct, sellPct);
  const leaderQty = leader === "buy" ? buy : sell;
  return {
    label: `${leaderPct.toFixed(0)}% ${leader}`,
    detail: `${buyPct.toFixed(0)}% buy / ${sellPct.toFixed(0)}% sell - ${fmtQty(leaderQty)} ${status.asset}`,
  };
}

function pressureTone(status) {
  const state = status.pressure_watch_state || "";
  const dir = status.pressure_watch_direction || "";
  if (state === "confirmed") return dir === "sell" ? "text-rose-300 border-rose-700/70 bg-rose-950/30" : "text-emerald-300 border-emerald-700/70 bg-emerald-950/30";
  if (state === "high_priority") return "text-amber-200 border-amber-600/70 bg-amber-950/40";
  if (state === "transition_risk") return "text-yellow-200 border-yellow-700/70 bg-yellow-950/30";
  return "text-amber-200 border-amber-800/60 bg-amber-950/20";
}

export default function RegimeCard({ status }) {
  const style = READ_STYLES[status.regime] || READ_STYLES.UNKNOWN;
  const readLabel = getMarketReadLabel(status.regime);
  const structureCopy = getMarketStructureCopy(status.regime);
  const cvm = status.cross_venue_multiplier ?? 1.0;
  const confirmation = cvm > 1.0 ? "confirmed" : cvm < 1.0 ? "single-venue" : "watching";
  const flow = getFlow(status);
  const readQuality = getReadQualityLabel(status);
  const lastUpdate = status.last_update_utc
    ? new Date(status.last_update_utc * 1000).toLocaleTimeString("en-US", { hour12: false })
    : "-";
  const pressureLabel = status.pressure_watch_state === "internal"
    ? ""
    : (status.pressure_watch_label || "");
  const pressureReasons = status.pressure_watch_reasons || [];
  const pressureDetail = pressureReasons[0] || "Watch for confirmation";
  const tradeState = status.trade_option_state || "";
  const tradeLabel = status.trade_option_label || "";
  const readiness = status.trade_option_readiness || 0;
  const blockers = status.trade_option_blockers || [];

  return (
    <div className={`rounded-lg border ${style.border} ${style.bg} p-3.5 mb-3 cursor-pointer hover:brightness-110 transition`}>
      <div className="flex items-center justify-between gap-2 mb-3">
        <div className="font-mono text-[15px] font-semibold text-slate-100">
          {status.asset}-USD <span className="text-slate-400 text-[13px] font-normal">on {status.venue}</span>
        </div>
        <span className={`px-2.5 py-1 rounded text-[11px] font-semibold text-white ${style.chip} whitespace-nowrap`}>
          {readLabel}
        </span>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-2">
        <Metric label="flow" value={flow.label} />
        <Metric label="volatility" value={fmtRealVol(status.realized_vol)} />
        <Metric label="read" value={readQuality} />
      </div>

      <div className="flex justify-between text-[11px] text-slate-400">
        <span>{confirmation}</span>
        <span>{lastUpdate} UTC</span>
      </div>

      <div className="mt-2 text-[11px] text-slate-400 italic">{flow.detail}</div>
      {pressureLabel && (
        <div className={`mt-2 rounded border px-2 py-1.5 text-[11px] leading-snug ${pressureTone(status)}`}>
          <div className="font-semibold">{pressureLabel}</div>
          <div className="opacity-80">{pressureDetail}</div>
        </div>
      )}
      <div className="mt-2 text-[12px] leading-snug text-slate-300">
        {structureCopy}
      </div>
      {tradeLabel && (
        <div className="mt-2 rounded border border-slate-700 bg-slate-950/50 px-2 py-1.5 text-[11px] text-slate-300">
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-slate-100">{tradeLabel}</span>
            <span className={tradeState === "early_probe" ? "text-amber-300" : tradeState === "confirmed" ? "text-emerald-300" : "text-slate-500"}>
              {readiness}/100
            </span>
          </div>
          <div className="mt-0.5 text-slate-400">
            {status.trade_option_size_hint || (blockers[0] || "review on tape")}
          </div>
        </div>
      )}

      <div className="mt-2.5 pt-2 border-t border-white/[0.06] flex items-center justify-end gap-1 text-xs font-medium text-slate-300">
        <span>Tap for live tape</span>
        <span className="text-slate-400">-&gt;</span>
      </div>
    </div>
  );
}

function Metric({ label, value }) {
  return (
    <div className="bg-slate-950/60 rounded px-2 py-1.5">
      <div className="text-slate-500 text-[10px] uppercase tracking-wider">{label}</div>
      <div className="font-mono text-[13px] text-slate-100">{value}</div>
    </div>
  );
}
