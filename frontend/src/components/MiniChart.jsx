import React, { useEffect, useState } from "react";
import { fetchChart } from "../api.js";

/**
 * Tiny inline chart for the RegimeCard. Two stacked rows:
 *   - last N minutes of price (sparkline)
 *   - last N minutes of buy / sell volume (offset bars)
 *
 * Polls the chart endpoint every ~10s. Tightly sized so the card stays
 * compact; renders empty if no data yet.
 */
export default function MiniChart({ asset, venue, nMinutes = 30, height = 36 }) {
  const [bars, setBars] = useState([]);

  useEffect(() => {
    let alive = true;
    async function tick() {
      try {
        const c = await fetchChart(asset, venue, nMinutes);
        if (alive) setBars((c && c.data) || []);
      } catch { /* leave previous */ }
    }
    tick();
    const t = setInterval(tick, 10000);
    return () => { alive = false; clearInterval(t); };
  }, [asset, venue, nMinutes]);

  if (!bars.length) return null;

  const prices = bars.map((b) => b.price);
  const minP = Math.min(...prices);
  const maxP = Math.max(...prices);
  const dx = 100 / Math.max(bars.length - 1, 1);
  const priceRange = Math.max(maxP - minP, 1e-9);

  const linePts = prices
    .map((p, i) => {
      const x = i * dx;
      const y = 100 - ((p - minP) / priceRange) * 100;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");

  const last = prices[prices.length - 1];
  const first = prices[0];
  const upish = last >= first;

  // volume bars
  const maxV = Math.max(1e-9, ...bars.map((b) => Math.max(b.buy_volume || 0, b.sell_volume || 0)));
  const barW = 100 / bars.length;

  return (
    <div className="select-none">
      <svg viewBox="0 0 100 100" preserveAspectRatio="none"
           style={{ width: "100%", height: `${height}px` }}>
        <polyline
          points={linePts}
          fill="none"
          stroke={upish ? "#34d399" : "#fb7185"}
          strokeWidth="1.5"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <svg viewBox="0 0 100 100" preserveAspectRatio="none"
           style={{ width: "100%", height: `${Math.round(height * 0.55)}px` }}>
        {bars.map((b, i) => {
          const x = i * barW;
          const buyH = ((b.buy_volume || 0) / maxV) * 50;     // top half
          const sellH = ((b.sell_volume || 0) / maxV) * 50;   // bottom half
          return (
            <g key={i}>
              <rect x={x} y={50 - buyH} width={Math.max(barW - 0.4, 0.3)}
                    height={buyH} fill="#10b981" opacity="0.65" />
              <rect x={x} y={50} width={Math.max(barW - 0.4, 0.3)}
                    height={sellH} fill="#f43f5e" opacity="0.65" />
            </g>
          );
        })}
        <line x1="0" y1="50" x2="100" y2="50" stroke="#475569" strokeWidth="0.4"
              vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
}
