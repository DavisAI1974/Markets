import React, { useState } from "react";
import { useStore } from "../store.js";
import RegimeCard from "../components/RegimeCard.jsx";
import LiveTape from "../components/LiveTape.jsx";
import { SkeletonCard, EmptyState } from "../components/LoadingSkeleton.jsx";

export default function LiveStatus() {
  const statuses = useStore((s) => s.statuses);
  const [showTape, setShowTape] = useState(true);

  if (!statuses) {
    return (
      <div>
        <SkeletonCard />
        <SkeletonCard />
      </div>
    );
  }
  if (statuses.length === 0) {
    return (
      <EmptyState
        icon="⏳"
        title="Waiting for the first regime read"
        body="The backend is collecting bins. The first card will appear about 30 seconds after the collectors start receiving trades."
      />
    );
  }

  // Group by asset for cleaner visual hierarchy
  const byAsset = {};
  for (const s of statuses) {
    (byAsset[s.asset] ||= []).push(s);
  }

  return (
    <div>
      <div className="flex justify-end mb-2">
        <button
          onClick={() => setShowTape(!showTape)}
          className="text-[11px] text-slate-400 hover:text-slate-200 px-2 py-0.5 rounded border border-slate-800"
        >
          {showTape ? "hide live tape" : "show live tape"}
        </button>
      </div>
      {Object.entries(byAsset).map(([asset, list]) => (
        <section key={asset} className="mb-6">
          <h2 className="text-xs uppercase tracking-wider text-slate-500 mb-2 px-1">{asset}</h2>
          {list.map((s) => (
            <div key={`${s.asset}-${s.venue}`}>
              <RegimeCard status={s} />
              {showTape && <LiveTape asset={s.asset} venue={s.venue} nMinutes={10} pollMs={5000} />}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}
