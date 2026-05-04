import React from "react";
import { useStore } from "../store.js";
import RegimeCard from "../components/RegimeCard.jsx";

export default function LiveStatus() {
  const statuses = useStore((s) => s.statuses);

  if (!statuses || statuses.length === 0) {
    return (
      <div className="text-slate-500 text-sm py-8 text-center">
        Waiting for the first regime classification (~30 seconds after backend starts collecting)…
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
      {Object.entries(byAsset).map(([asset, list]) => (
        <section key={asset} className="mb-6">
          <h2 className="text-xs uppercase tracking-wider text-slate-500 mb-2 px-1">{asset}</h2>
          {list.map((s) => (
            <RegimeCard key={`${s.asset}-${s.venue}`} status={s} />
          ))}
        </section>
      ))}
    </div>
  );
}
