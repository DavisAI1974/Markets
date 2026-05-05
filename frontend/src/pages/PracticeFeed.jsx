import React, { useEffect, useState } from "react";
import { fetchPracticeTrades, closePracticeTrade } from "../api.js";
import { SkeletonCard, EmptyState } from "../components/LoadingSkeleton.jsx";
import { usePullToRefresh, PullIndicator } from "../usePullToRefresh.js";

function fmtPrice(p) {
  if (!p) return "—";
  if (p >= 1000) return "$" + p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 1)    return "$" + p.toFixed(4);
  return "$" + p.toFixed(6);
}
function fmtUsd(v) {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "−";
  return `${sign}$${Math.abs(v).toFixed(2)}`;
}
function fmtQty(q) {
  if (!q) return "0";
  if (q >= 1000) return q.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (q >= 1)    return q.toFixed(3);
  return q.toFixed(6);
}

export default function PracticeFeed() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [closing, setClosing] = useState(null);

  async function refresh() {
    try {
      const r = await fetchPracticeTrades(200);
      setData(r);
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, []);
  const ptr = usePullToRefresh(refresh);

  async function close(intentId) {
    setClosing(intentId);
    try {
      await closePracticeTrade(intentId);
      await refresh();
    } catch (e) {
      setError(String(e));
    }
    setClosing(null);
  }

  if (error) return <div className="text-rose-400 text-sm">{error}</div>;
  if (!data) return (
    <div>
      <SkeletonCard heightCls="h-24" />
      <SkeletonCard heightCls="h-32" />
    </div>
  );

  const trades = data.trades || [];
  const open = trades.filter((t) => t.status === "open");
  const closed = trades.filter((t) => t.status === "closed");
  const totalRealized = data.total_realized_pnl_usd || 0;
  const winRate = data.win_rate;

  return (
    <div className="space-y-4">
      <PullIndicator {...ptr} />
      <div className="rounded border border-sky-800 bg-sky-950/40 p-3">
        <div className="text-xs uppercase tracking-wide text-sky-300/80 font-bold">
          Practice mode
        </div>
        <p className="text-xs text-sky-200/80 mt-1 leading-relaxed">
          Practice trades simulate fills against the live bid/ask with a 25 bp
          symmetric fee. No real money at risk. Use this to learn the workflow
          and your reactions before flipping the header toggle to Live.
        </p>
      </div>

      <div className="grid grid-cols-3 gap-2">
        <Stat label="open" value={data.n_open} />
        <Stat label="closed" value={data.n_closed} sub={winRate !== null ? `${(winRate * 100).toFixed(0)}% win rate` : null} />
        <Stat
          label="total P&L"
          value={fmtUsd(totalRealized)}
          big
          accent={totalRealized >= 0 ? "emerald" : "rose"}
        />
      </div>

      <section>
        <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2 px-1">
          Open positions ({open.length})
        </h3>
        {open.length === 0 ? (
          <div className="text-slate-500 text-sm italic py-4 text-center">
            No open practice trades. Tap a bid/ask cell on the Live tab to enter one.
          </div>
        ) : (
          open.map((t) => <OpenTrade key={t.intent_id} t={t} onClose={() => close(t.intent_id)} closing={closing === t.intent_id} />)
        )}
      </section>

      {closed.length > 0 && (
        <section>
          <h3 className="text-xs uppercase tracking-wider text-slate-500 mb-2 px-1">
            Closed ({closed.length})
          </h3>
          {closed.slice(0, 50).map((t) => <ClosedTrade key={t.intent_id} t={t} />)}
        </section>
      )}
    </div>
  );
}

function OpenTrade({ t, onClose, closing }) {
  const sideColor = t.side === "buy" ? "text-emerald-400" : "text-rose-400";
  const unreal = t.unrealized_pnl_usd;
  const pnlColor = unreal == null ? "text-slate-400" : unreal >= 0 ? "text-emerald-400" : "text-rose-400";
  const opened = new Date(t.ts_utc * 1000).toLocaleTimeString("en-US", { hour12: false });

  return (
    <div className="bg-slate-900 rounded border border-slate-800 p-3 mb-2">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className={`font-mono text-sm font-bold ${sideColor}`}>
            {t.side === "buy" ? "LONG" : "SHORT"}
          </span>
          <span className="font-mono text-sm text-slate-100 ml-2">
            {fmtQty(t.qty)} {t.asset}
          </span>
          <span className="text-xs text-slate-500 ml-2">on {t.venue}</span>
          <div className="text-xs text-slate-400 font-mono mt-1">
            entry {fmtPrice(t.fill_price)} · mark {fmtPrice(t.mark_price)} · opened {opened}
          </div>
        </div>
        <div className="text-right">
          <div className={`font-mono text-sm font-bold ${pnlColor}`}>
            {fmtUsd(unreal)}
          </div>
          <div className="text-[10px] text-slate-500">unrealized</div>
        </div>
      </div>
      {t.note && <div className="text-xs text-slate-500 italic mt-2">"{t.note}"</div>}
      <button
        onClick={onClose}
        disabled={closing}
        className="mt-2 w-full rounded bg-slate-800 hover:bg-slate-700 px-3 py-1.5 text-xs text-slate-100 disabled:opacity-40"
      >
        {closing ? "Closing…" : "Close at market"}
      </button>
    </div>
  );
}

function ClosedTrade({ t }) {
  const sideColor = t.side === "buy" ? "text-emerald-400" : "text-rose-400";
  const real = t.realized_pnl_usd || 0;
  const pnlColor = real >= 0 ? "text-emerald-400" : "text-rose-400";
  const opened = new Date(t.ts_utc * 1000).toLocaleTimeString("en-US", { hour12: false });
  const closed = t.exit_ts_utc ? new Date(t.exit_ts_utc * 1000).toLocaleTimeString("en-US", { hour12: false }) : "—";
  const heldS = t.exit_ts_utc ? Math.round(t.exit_ts_utc - t.ts_utc) : 0;

  return (
    <div className="bg-slate-900/60 rounded border border-slate-800 p-2 mb-1.5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className={`font-mono text-xs font-bold ${sideColor}`}>
            {t.side === "buy" ? "LONG" : "SHORT"}
          </span>
          <span className="font-mono text-xs text-slate-200 ml-2">
            {fmtQty(t.qty)} {t.asset}
          </span>
          <span className="text-[10px] text-slate-500 ml-2">on {t.venue}</span>
          <div className="text-[10px] text-slate-500 font-mono mt-0.5">
            {fmtPrice(t.fill_price)} → {fmtPrice(t.exit_price)} · {opened}–{closed} · held {Math.floor(heldS/60)}m{heldS%60}s
          </div>
        </div>
        <div className={`font-mono text-sm font-bold ${pnlColor}`}>
          {fmtUsd(real)}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, sub, big, accent }) {
  const accentCls = accent === "emerald" ? "text-emerald-400"
    : accent === "rose" ? "text-rose-400"
    : "text-slate-100";
  return (
    <div className="bg-slate-900 rounded p-3 border border-slate-800">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`font-mono ${big ? "text-2xl" : "text-base"} mt-1 ${accentCls}`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-500 mt-1">{sub}</div>}
    </div>
  );
}
