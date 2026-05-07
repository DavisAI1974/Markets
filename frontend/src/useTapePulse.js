import { useEffect, useRef, useState } from "react";
import { fetchTape } from "./api.js";

/**
 * Polls the 1-sec resolution tape feed at ~1Hz and exposes a "pulse"
 * that the UI uses to flash the bid/ask cell whenever a new aggressor
 * hit lands. Each new sec-bin with buy_volume > 0 → bumps `buyPulse`,
 * which the UI listens to and triggers a brief flash on the ask cell.
 * Each with sell_volume > 0 → `sellPulse` → flash on the bid cell.
 *
 * Returns:
 *   { buyPulse, sellPulse, latestBid, latestAsk, latestPrice, latestNTrades }
 *
 * Pulses are integers that increment each time activity is detected on
 * that side; consumers use them with a useEffect dependency so any
 * change triggers their effect.
 */
export function useTapePulse(asset, venue, { pollMs = 1000, lookbackS = 30 } = {}) {
  const [state, setState] = useState({
    buyPulse: 0,
    sellPulse: 0,
    latestBid: 0,
    latestAsk: 0,
    latestPrice: 0,
    latestNTrades: 0,
    error: null,
  });
  const lastSeenTs = useRef(0);

  useEffect(() => {
    if (!asset || !venue) return;   // disabled / static mode
    let alive = true;
    async function tick() {
      try {
        const r = await fetchTape(asset, venue, lookbackS);
        if (!alive) return;
        const data = r.data || [];
        if (data.length === 0) return;
        // Only consider sec-bins newer than the last one we already
        // accounted for, so successive polls don't double-count.
        const fresh = data.filter((b) => b.ts > lastSeenTs.current);
        if (fresh.length === 0) return;
        lastSeenTs.current = fresh[fresh.length - 1].ts;

        let addBuy = 0, addSell = 0;
        for (const b of fresh) {
          if (b.buy > 0) addBuy++;
          if (b.sell > 0) addSell++;
        }
        const last = data[data.length - 1];
        setState((s) => ({
          buyPulse:  s.buyPulse  + addBuy,
          sellPulse: s.sellPulse + addSell,
          latestBid: last.bid || s.latestBid,
          latestAsk: last.ask || s.latestAsk,
          latestPrice: last.mid || last.bid && last.ask
            ? (last.mid || (last.bid + last.ask) / 2)
            : s.latestPrice,
          latestNTrades: last.n_trades || 0,
          error: null,
        }));
      } catch (e) {
        if (alive) setState((s) => ({ ...s, error: String(e) }));
      }
    }
    tick();
    const t = setInterval(tick, pollMs);
    return () => { alive = false; clearInterval(t); };
  }, [asset, venue, pollMs, lookbackS]);

  return state;
}
