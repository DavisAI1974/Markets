import React, { useEffect, useState } from "react";
import { fetchStats } from "../api.js";
import { EmptyState, SkeletonCard } from "../components/LoadingSkeleton.jsx";

export default function Stats() {
  const [data, setData] = useState(null);
  const [windowHours, setWindowHours] = useState(24);
  const [error, setError] = useState(null);

  useEffect(() => {
    setError(null);
    fetchStats(windowHours)
      .then((j) => {
        setData(normalizeStats(j));
        setError(null);
      })
      .catch((e) => setError(e.message));
    const t = setInterval(() => {
      fetchStats(windowHours)
        .then((j) => {
          setData(normalizeStats(j));
          setError(null);
        })
        .catch(() => {});
    }, 30000);
    return () => clearInterval(t);
  }, [windowHours]);

  if (error && !data) {
    return (
      <EmptyState
        icon="!"
        title="Stats are not available yet"
        body="The live stats endpoint did not return a usable response. The rest of the app can keep running while this view waits for analytics data."
      />
    );
  }
  if (!data) return <SkeletonCard heightCls="h-64" />;

  const cvTotal = data.cross_venue_confirmed + data.cross_venue_disagreed;
  const cvRate = cvTotal > 0 ? data.cross_venue_confirmed / cvTotal : 0;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xs uppercase tracking-wider text-slate-500">Stats</h2>
        <select
          value={windowHours}
          onChange={(e) => setWindowHours(parseInt(e.target.value))}
          className="bg-slate-900 border border-slate-700 rounded px-2 py-1 text-xs"
        >
          <option value={1}>last 1h</option>
          <option value={6}>last 6h</option>
          <option value={24}>last 24h</option>
          <option value={168}>last 7d</option>
          <option value={720}>last 30d</option>
        </select>
      </div>

      <section className="grid grid-cols-3 gap-2">
        <Stat label="signals" value={data.n_signals} big />
        <Stat label="cross-venue ✓" value={`${(cvRate * 100).toFixed(0)}%`}
               sub={`${data.cross_venue_confirmed} / ${cvTotal}`} />
        <Stat label="avg read score" value={`${(data.avg_adjusted_confidence * 100).toFixed(0)}%`} />
      </section>

      {data.outcomes && (data.outcomes.resolved > 0 || data.outcomes.pending > 0) && (
        <section>
          <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2">Realized outcomes</h3>
          <div className="grid grid-cols-3 gap-2 mb-3">
            <Stat
              label="resolved"
              value={data.outcomes.resolved}
              sub={`${data.outcomes.pending} pending · ${data.outcomes.abandoned} abandoned`}
            />
            <Stat
              label="win rate"
              value={data.outcomes.win_rate !== null ? `${(data.outcomes.win_rate * 100).toFixed(0)}%` : "—"}
              big
            />
            <Stat
              label="total P&L"
              value={data.outcomes.total_realized_bps !== null
                ? `${data.outcomes.total_realized_bps >= 0 ? "+" : ""}${data.outcomes.total_realized_bps.toFixed(1)}bp`
                : "—"}
              sub={data.outcomes.avg_realized_bps !== null
                ? `avg ${data.outcomes.avg_realized_bps >= 0 ? "+" : ""}${data.outcomes.avg_realized_bps.toFixed(1)}bp/trade`
                : null}
            />
          </div>
          {data.outcomes.by_source_pnl && Object.keys(data.outcomes.by_source_pnl).length > 0 && (
            <div className="bg-slate-900 rounded p-3 text-xs space-y-1.5">
              <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-1">By source</div>
              {Object.entries(data.outcomes.by_source_pnl).map(([key, p]) => {
                const wp = p.n > 0 ? (p.wins / p.n) : 0;
                return (
                  <div key={key} className="flex items-center justify-between gap-3 font-mono">
                    <div className="text-slate-300 w-28 truncate">{key}</div>
                    <div className="text-slate-400">n={p.n}</div>
                    <div className="text-slate-400">{(wp * 100).toFixed(0)}%</div>
                    <div className={p.total_bps >= 0 ? "text-green-400" : "text-red-400"}>
                      {p.total_bps >= 0 ? "+" : ""}{p.total_bps.toFixed(1)}bp
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}

      <section>
        <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2">By setup</h3>
        <DistBar entries={Object.entries(data.by_regime)} colors={REGIME_COLORS} />
      </section>

      {data.pressure_watch && (
        <section>
          <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2">Pressure watch</h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-slate-900 rounded p-3 border border-slate-800">
              <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-2">Signals by pressure state</div>
              <DistBar entries={Object.entries(data.pressure_watch.by_state || {})} colors={PRESSURE_COLORS} />
            </div>
            <div className="bg-slate-900 rounded p-3 border border-slate-800">
              <div className="text-slate-500 uppercase tracking-wider text-[10px] mb-2">Outcomes by pressure state</div>
              <PressureOutcomeTable rows={data.pressure_watch.outcomes_by_state || {}} />
            </div>
          </div>
        </section>
      )}

      <section>
        <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2">By source</h3>
        <DistBar entries={Object.entries(data.by_source)} colors={null} />
      </section>

      {data.n_signals === 0 && (
        <p className="text-slate-500 text-sm italic mt-6">
          No signals in this window yet. Most market activity is healthy
          two-sided trading (baseline). Signals fire when we detect a big
          whale buyer, whale seller, herd move, or wash pattern.
        </p>
      )}
    </div>
  );
}

function normalizeStats(raw) {
  const data = raw || {};
  return {
    ...data,
    n_signals: data.n_signals ?? 0,
    cross_venue_confirmed: data.cross_venue_confirmed ?? 0,
    cross_venue_disagreed: data.cross_venue_disagreed ?? 0,
    avg_adjusted_confidence: data.avg_adjusted_confidence ?? 0,
    by_regime: data.by_regime || {},
    by_source: data.by_source || {},
    pressure_watch: data.pressure_watch || null,
    outcomes: data.outcomes || null,
  };
}

const REGIME_COLORS = {
  WHALE_UP: "bg-green-700",
  WHALE_DOWN: "bg-red-700",
  HERD_UP: "bg-orange-600",
  HERD_DOWN: "bg-rose-700",
  EQUILIBRIUM_TWO_SIDED: "bg-blue-700",
  EQUILIBRIUM_EXTREME_DEMO: "bg-blue-900 border border-blue-500",
  WASH_PAIRED: "bg-yellow-700",
  WASH_HAWKES: "bg-yellow-700",
  DEPLETED: "bg-gray-600",
  UNKNOWN: "bg-slate-700",
};

const PRESSURE_COLORS = {
  none: "bg-slate-700",
  internal: "bg-amber-900",
  forming: "bg-amber-600",
  transition_risk: "bg-yellow-600",
  high_priority: "bg-orange-500",
  confirmed: "bg-emerald-600",
};

function PressureOutcomeTable({ rows }) {
  const entries = Object.entries(rows);
  if (entries.length === 0) {
    return <div className="text-slate-500 text-xs italic">no resolved outcomes yet</div>;
  }
  return (
    <div className="space-y-1.5 text-xs">
      {entries.map(([state, row]) => (
        <div key={state} className="grid grid-cols-[1fr_2.5rem_3rem_4rem] gap-2 font-mono">
          <span className="truncate text-slate-300">{state}</span>
          <span className="text-slate-400 text-right">n={row.n}</span>
          <span className="text-slate-400 text-right">
            {row.win_rate != null ? `${(row.win_rate * 100).toFixed(0)}%` : "-"}
          </span>
          <span className={row.total_bps >= 0 ? "text-green-400 text-right" : "text-red-400 text-right"}>
            {row.total_bps >= 0 ? "+" : ""}{Number(row.total_bps || 0).toFixed(1)}bp
          </span>
        </div>
      ))}
    </div>
  );
}

function Stat({ label, value, sub, big }) {
  return (
    <div className="bg-slate-900 rounded p-3 border border-slate-800">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`font-mono ${big ? "text-2xl" : "text-base"} mt-1`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-500 mt-1">{sub}</div>}
    </div>
  );
}

function DistBar({ entries, colors }) {
  const total = entries.reduce((acc, [, n]) => acc + n, 0);
  if (total === 0) return <div className="text-slate-500 text-xs italic">no data</div>;
  return (
    <div className="space-y-1.5">
      {entries.map(([name, n]) => {
        const pct = (n / total) * 100;
        const cls = colors ? (colors[name] || "bg-slate-600") : "bg-slate-600";
        return (
          <div key={name} className="flex items-center text-xs gap-2">
            <div className="w-40 truncate font-mono text-slate-300">{name}</div>
            <div className="flex-1 bg-slate-900 rounded h-4 relative overflow-hidden">
              <div className={`h-full ${cls}`} style={{ width: `${pct}%` }} />
            </div>
            <div className="w-12 text-right font-mono text-slate-400">{n}</div>
          </div>
        );
      })}
    </div>
  );
}
