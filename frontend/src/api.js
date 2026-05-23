import { useStore } from "./store.js";

const BASE = "/mw";   // proxied via vite in dev; neutral path avoids browser API filters

export async function fetchStatus() {
  if (window.__MW_LIVE__?.statuses?.length) {
    return window.__MW_LIVE__;
  }
  const mod = await import(/* @vite-ignore */ `/assets/mw-live.mjs?t=${Date.now()}`);
  return mod.default;
}

export async function fetchSignals(limit = 50) {
  const r = await fetch(`${BASE}/signals?limit=${limit}`);
  if (!r.ok) throw new Error(`signals ${r.status}`);
  return r.json();
}

export async function fetchSignalDetail(signalId) {
  const r = await fetch(`${BASE}/signal/${signalId}`);
  if (!r.ok) throw new Error(`signal detail ${r.status}`);
  return r.json();
}

export async function fetchChart(asset, venue, nMinutes = 240) {
  const key = `${asset}/${venue}`.toLowerCase();
  const preloaded = window.__MW_LIVE__?.tapes?.[key];
  if (preloaded?.data?.length) {
    const byMinute = new Map();
    for (const b of preloaded.data) {
      const ts = Math.floor(b.ts / 60) * 60;
      const row = byMinute.get(ts) || {
        ts,
        price: b.mid || 0,
        bid: b.bid || 0,
        ask: b.ask || 0,
        buy_volume: 0,
        sell_volume: 0,
        n_trades: 0,
        last_aggressor: "",
        high: b.mid || 0,
        low: b.mid || 0,
      };
      const mid = b.mid || row.price;
      row.price = mid;
      row.bid = b.bid || row.bid;
      row.ask = b.ask || row.ask;
      row.buy_volume += b.buy || 0;
      row.sell_volume += b.sell || 0;
      row.n_trades += b.n_trades || 0;
      row.last_aggressor = b.last_aggressor || row.last_aggressor;
      if (mid) {
        row.high = row.high ? Math.max(row.high, mid) : mid;
        row.low = row.low ? Math.min(row.low, mid) : mid;
      }
      byMinute.set(ts, row);
    }
    const data = Array.from(byMinute.values()).sort((a, b) => a.ts - b.ts).slice(-nMinutes);
    return { asset, venue, n_points: data.length, data };
  }
  const r = await fetch(`${BASE}/chart/${asset}/${venue}?n_minutes=${nMinutes}`);
  if (!r.ok) throw new Error(`chart ${r.status}`);
  return r.json();
}

/** 1-second resolution tape feed. UI polls this at ~1Hz to flash the
 *  bid/ask cell on each new aggressor hit. */
export async function fetchTape(asset, venue, nSeconds = 30) {
  const key = `${asset}/${venue}`.toLowerCase();
  const preloaded = window.__MW_LIVE__?.tapes?.[key];
  if (preloaded?.data?.length) {
    const data = preloaded.data;
    const cutoff = data[data.length - 1].ts - nSeconds;
    return { ...preloaded, data: data.filter((b) => b.ts >= cutoff) };
  }
  const r = await fetch(`${BASE}/tape/${asset}/${venue}?n_seconds=${nSeconds}`);
  if (!r.ok) throw new Error(`tape ${r.status}`);
  return r.json();
}

export async function fetchStats(windowHours = 24) {
  const r = await fetch(`${BASE}/stats?window_hours=${windowHours}`);
  if (!r.ok) throw new Error(`stats ${r.status}`);
  return r.json();
}

export async function fetchAutoTradeSettings() {
  const r = await fetch(`${BASE}/auto-trade-settings`);
  if (!r.ok) throw new Error(`auto-trade-settings ${r.status}`);
  return r.json();
}

export async function postAutoTradeSettings(settings) {
  const r = await fetch(`${BASE}/auto-trade-settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!r.ok) throw new Error(`auto-trade-settings ${r.status}`);
  return r.json();
}

export async function fetchEvolveRequests(limit = 20) {
  const r = await fetch(`${BASE}/evolve-requests?limit=${limit}`);
  if (!r.ok) throw new Error(`evolve-requests ${r.status}`);
  return r.json();
}

export async function postEvolveRequest({ prompt, mode, source = "evolve_tab" }) {
  const r = await fetch(`${BASE}/evolve-request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, mode, source }),
  });
  if (!r.ok) throw new Error(`evolve-request ${r.status}`);
  return r.json();
}

export async function fetchRegimeHistory(asset, venue, nPoints = 60) {
  const r = await fetch(`${BASE}/regime_history/${asset}/${venue}?n_points=${nPoints}`);
  if (!r.ok) throw new Error(`regime history ${r.status}`);
  return r.json();
}

/** Subscribe to SSE stream. Returns a cleanup fn. */
export function subscribeToStream({ onSignal, onSnapshot, onDriftAlert, onError }) {
  const es = new EventSource(`${BASE}/stream`);
  es.addEventListener("signal", (e) => { try { onSignal && onSignal(JSON.parse(e.data)); } catch {} });
  es.addEventListener("snapshot", (e) => { try { onSnapshot && onSnapshot(JSON.parse(e.data)); } catch {} });
  es.addEventListener("drift_alert", (e) => { try { onDriftAlert && onDriftAlert(JSON.parse(e.data)); } catch {} });
  es.addEventListener("heartbeat", () => { /* no-op; just keeps connection alive */ });
  es.onerror = (e) => onError && onError(e);
  return () => es.close();
}

export async function fetchDriftAlerts(limit = 50) {
  const r = await fetch(`${BASE}/drift-alerts?limit=${limit}`);
  if (!r.ok) throw new Error(`drift-alerts ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Web Push subscription helpers
// ---------------------------------------------------------------------------

export async function fetchVapidPublicKey() {
  const r = await fetch(`${BASE}/push/vapid-public-key`);
  if (!r.ok) throw new Error(`vapid-public-key ${r.status}`);
  return r.json();
}

export async function postPushSubscription(subscription) {
  const subJson = subscription.toJSON();
  const r = await fetch(`${BASE}/push/subscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      endpoint: subJson.endpoint,
      p256dh: subJson.keys.p256dh,
      auth: subJson.keys.auth,
      user_agent: navigator.userAgent,
    }),
  });
  if (!r.ok) throw new Error(`push/subscribe ${r.status}`);
  return r.json();
}

export async function postPushUnsubscribe(endpoint) {
  const r = await fetch(`${BASE}/push/unsubscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ endpoint, p256dh: "", auth: "" }),
  });
  if (!r.ok) throw new Error(`push/unsubscribe ${r.status}`);
  return r.json();
}

// ---------------------------------------------------------------------------
// Manual-trade intent — records click-to-trade events for audit. The user
// then executes on their own exchange; this endpoint never holds keys.
// ---------------------------------------------------------------------------

export async function postManualTradeIntent({ asset, venue, side, price, qty, note, practice }) {
  const r = await fetch(`${BASE}/manual-trade-intent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      asset, venue, side, price, qty,
      note: note || "",
      practice: practice !== false,   // default true — practice unless explicitly false
    }),
  });
  if (!r.ok) throw new Error(`manual-trade-intent ${r.status}`);
  return r.json();
}

export async function fetchPracticeTrades(limit = 100) {
  const r = await fetch(`${BASE}/practice-trades?limit=${limit}`);
  if (!r.ok) throw new Error(`practice-trades ${r.status}`);
  return r.json();
}

export async function fetchMockTradeSettings() {
  const r = await fetch(`${BASE}/mock-trade-settings`);
  if (!r.ok) throw new Error(`mock-trade-settings ${r.status}`);
  return r.json();
}

export async function postMockTradeSettings(settings) {
  const r = await fetch(`${BASE}/mock-trade-settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!r.ok) throw new Error(`mock-trade-settings ${r.status}`);
  return r.json();
}

export async function closePracticeTrade(intentId) {
  const r = await fetch(`${BASE}/practice-trade/close`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intent_id: intentId }),
  });
  if (!r.ok) throw new Error(`practice-trade/close ${r.status}`);
  return r.json();
}
