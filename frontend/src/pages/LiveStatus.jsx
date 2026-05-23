import React from "react";
import { Link } from "react-router-dom";
import { useStore } from "../store.js";
import RegimeCard from "../components/RegimeCard.jsx";
import { EmptyState } from "../components/LoadingSkeleton.jsx";

export default function LiveStatus() {
  const statuses = useStore((s) => s.statuses);
  const lastError = useStore((s) => s.lastError);

  if (!statuses || statuses.length === 0) {
    return (
      <div>
        {lastError && (
          <div className="mb-3 rounded border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-100">
            Live data check: {lastError}
          </div>
        )}
        <EmptyState
          icon="●"
          title="Waiting for live market reads"
          body="The app is connected and waiting for the first market read. Once venues report enough flow, the strongest Whale, Herd, and Equilibrium reads will appear here automatically."
          action={
            <div className="flex flex-wrap justify-center gap-2">
              <Link className="rounded bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-100 hover:bg-slate-700" to="/signals">
                View signals
              </Link>
              <Link className="rounded border border-slate-700 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:border-slate-500" to="/practice">
                Practice mode
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  // Group by asset for cleaner visual hierarchy
  const byAsset = {};
  for (const s of statuses) {
    (byAsset[s.asset] ||= []).push(s);
  }

  return (
    <div>
      <div className="mb-4 rounded-lg border border-slate-800 bg-slate-900/40 p-3">
        <div className="text-xs uppercase tracking-wider text-slate-500">Live command center</div>
        <div className="mt-1 text-sm text-slate-300">
          Ranked by asset and venue. Each read separates big-player pressure from herd movement, then opens into the live tape, quote action, and practice ticket.
        </div>
      </div>
      {Object.entries(byAsset).map(([asset, list]) => (
        <section key={asset} className="mb-6">
          <h2 className="text-xs uppercase tracking-wider text-slate-500 mb-2 px-1">{asset}</h2>
          {list.map((s) => (
            <Link
              key={`${s.asset}-${s.venue}`}
              to={`/tape/${s.asset}/${s.venue}`}
              className="block no-underline text-inherit"
            >
              <RegimeCard status={s} />
            </Link>
          ))}
        </section>
      ))}
    </div>
  );
}
