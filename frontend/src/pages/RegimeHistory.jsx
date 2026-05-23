import React, { useEffect, useState } from "react";
import { useStore } from "../store.js";
import { fetchRegimeHistory } from "../api.js";
import { getReadQualityLabel } from "../marketReadCopy.js";

const REGIME_COLORS = {
  EQUILIBRIUM_TWO_SIDED: "bg-blue-600",
  WHALE_UP: "bg-green-600",
  WHALE_DOWN: "bg-red-600",
  HERD_UP: "bg-orange-500",
  HERD_DOWN: "bg-rose-700",
  WASH_PAIRED: "bg-yellow-600",
  WASH_HAWKES: "bg-yellow-600",
  DEPLETED: "bg-gray-500",
  UNKNOWN: "bg-slate-500",
};

const REGIME_SHORT = {
  EQUILIBRIUM_TWO_SIDED: "EQ",
  WHALE_UP: "W↑",
  WHALE_DOWN: "W↓",
  HERD_UP: "H↑",
  HERD_DOWN: "H↓",
  WASH_PAIRED: "WS",
  WASH_HAWKES: "WS",
  DEPLETED: "—",
  UNKNOWN: "?",
};

const READ_LABELS = {
  EQUILIBRIUM_TWO_SIDED: "Equilibrium",
  WHALE_UP: "Whale buyer",
  WHALE_DOWN: "Whale seller",
  HERD_UP: "Herd buying",
  HERD_DOWN: "Herd selling",
  WASH_PAIRED: "Suspect flow",
  WASH_HAWKES: "Suspect flow",
  DEPLETED: "Quiet",
  UNKNOWN: "Watching",
};

const PRESSURE_RING = {
  internal: "ring-1 ring-amber-900/70",
  forming: "ring-2 ring-amber-400",
  transition_risk: "ring-2 ring-yellow-400",
  high_priority: "ring-2 ring-orange-300",
  confirmed: "ring-2 ring-emerald-300",
};

export default function RegimeHistory() {
  const statuses = useStore((s) => s.statuses);
  const [historyByKey, setHistoryByKey] = useState({});

  useEffect(() => {
    if (!statuses || statuses.length === 0) return;
    statuses.forEach((s) => {
      const key = `${s.asset}-${s.venue}`;
      fetchRegimeHistory(s.asset, s.venue, 50)
        .then((d) => setHistoryByKey((prev) => ({ ...prev, [key]: d })))
        .catch(() => {});
    });
    const t = setInterval(() => {
      statuses.forEach((s) => {
        const key = `${s.asset}-${s.venue}`;
        fetchRegimeHistory(s.asset, s.venue, 50)
          .then((d) => setHistoryByKey((prev) => ({ ...prev, [key]: d })))
          .catch(() => {});
      });
    }, 60000);
    return () => clearInterval(t);
  }, [statuses?.length]);

  if (!statuses || statuses.length === 0) {
    return <div className="text-slate-500 text-sm py-8 text-center">Waiting for data…</div>;
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xs uppercase tracking-wider text-slate-500">Market read history (last 50 chunks per source)</h2>
      {statuses.map((s) => {
        const key = `${s.asset}-${s.venue}`;
        const h = historyByKey[key];
        const points = normalizeHistoryPoints(h);
        const totalChunks = h?.n_chunks_total ?? h?.n_total ?? points.length;
        return (
          <section key={key}>
            <div className="flex items-center justify-between mb-1.5">
              <h3 className="font-mono text-sm">
                {s.asset}-USD <span className="text-slate-500">on {s.venue}</span>
              </h3>
              {h && <span className="text-[10px] text-slate-500">{totalChunks} total chunks</span>}
            </div>
            {!h ? (
              <div className="text-slate-500 text-xs italic">loading…</div>
            ) : points.length === 0 ? (
              <div className="text-slate-500 text-xs italic">no chunks yet</div>
            ) : (
              <RegimeStrip points={points} />
            )}
          </section>
        );
      })}
    </div>
  );
}

function normalizeHistoryPoints(history) {
  if (!history) return [];
  const points = Array.isArray(history.points)
    ? history.points
    : Array.isArray(history.history)
      ? history.history
      : [];

  return points
    .filter(Boolean)
    .map((p) => ({
      ...p,
      ts_start: p.ts_start ?? p.ts ?? p.timestamp ?? null,
      regime: p.regime || "UNKNOWN",
      confidence: Number.isFinite(p.confidence) ? p.confidence : 0,
      pressure_watch_state: p.pressure_watch_state || "",
      pressure_watch_label: p.pressure_watch_label || "",
    }));
}

function RegimeStrip({ points }) {
  return (
    <div className="bg-slate-900 rounded p-2 border border-slate-800">
      <div className="flex gap-0.5 overflow-x-auto">
        {points.map((p, i) => {
          const cls = REGIME_COLORS[p.regime] || "bg-slate-700";
          const pressureCls = PRESSURE_RING[p.pressure_watch_state] || "";
          const lbl = REGIME_SHORT[p.regime] || "?";
          const ts = p.ts_start
            ? new Date(p.ts_start * 1000).toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit" })
            : "--:--";
          const pressureText = p.pressure_watch_label
            ? ` · ${p.pressure_watch_label}`
            : "";
          return (
            <div
              key={i}
              className={`flex-shrink-0 w-8 h-10 ${cls} ${pressureCls} rounded text-[10px] flex flex-col items-center justify-center font-mono`}
              title={`${READ_LABELS[p.regime] || READ_LABELS.UNKNOWN}${pressureText} @ ${ts} (read ${getReadQualityLabel(p)})`}
            >
              <div className="text-white">{lbl}</div>
              <div className="text-white/60 text-[8px]">{ts.slice(0, 5)}</div>
            </div>
          );
        })}
      </div>
      <div className="text-[10px] text-slate-500 mt-2 flex flex-wrap gap-2">
        {Object.entries(REGIME_SHORT).map(([k, v]) => (
          <span key={k}><span className={`inline-block w-3 h-3 mr-1 rounded ${REGIME_COLORS[k]}`} />{v} {READ_LABELS[k] || READ_LABELS.UNKNOWN}</span>
        ))}
        <span><span className="inline-block w-3 h-3 mr-1 rounded bg-slate-800 ring-2 ring-amber-400" />pressure watch</span>
      </div>
    </div>
  );
}
