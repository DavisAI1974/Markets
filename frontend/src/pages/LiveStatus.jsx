import React, { useState } from "react";
import { useStore } from "../store.js";
import RegimeCard from "../components/RegimeCard.jsx";
import LiveTape from "../components/LiveTape.jsx";

export default function LiveStatus() {
  const statuses = useStore((s) => s.statuses);
  const [showTape, setShowTape] = useState(true);

  if (!statuses || statuses.length === 0) {
    return (
      <div className="text-slate-500 text-sm py-8 text-center">
        Waiting for the first regime read (~30 seconds after backend starts collecting)…
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
