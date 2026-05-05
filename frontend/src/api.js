import { useStore } from "./store.js";

const BASE = "";   // proxied via vite in dev; same-origin in prod

export async function fetchStatus() {
  const r = await fetch(`${BASE}/api/status`);
  if (!r.ok) throw new Error(`status ${r.status}`);
  return r.json();
}

export async function fetchSignals(limit = 50) {
  const r = await fetch(`${BASE}/api/signals?limit=${limit}`);
  if (!r.ok) throw new Error(`signals ${r.status}`);
  return r.json();
}

export async function fetchSignalDetail(signalId) {
  const r = await fetch(`${BASE}/api/signal/${signalId}`);
  if (!r.ok) throw new Error(`signal detail ${r.status}`);
  return r.json();
}

export async function fetchChart(asset, venue, nMinutes = 240) {
  const r = await fetch(`${BASE}/api/chart/${asset}/${venue}?n_minutes=${nMinutes}`);
  if (!r.ok) throw new Error(`chart ${r.status}`);
  return r.json();
}

export async function fetchStats(windowHours = 24) {
  const r = await fetch(`${BASE}/api/stats?window_hours=${windowHours}`);
  if (!r.ok) throw new Error(`stats ${r.status}`);
  return r.json();
}

export async function fetchRegimeHistory(asset, venue, nPoints = 60) {
  const r = await fetch(`${BASE}/api/regime_history/${asset}/${venue}?n_points=${nPoints}`);
  if (!r.ok) throw new Error(`regime history ${r.status}`);
  return r.json();
}

/** Subscribe to SSE stream. Returns a cleanup fn. */
export function subscribeToStream({ onSignal, onSnapshot, onError }) {
  const es = new EventSource(`${BASE}/api/stream`);
  es.addEventListener("signal", (e) => { try { onSignal && onSignal(JSON.parse(e.data)); } catch {} });
  es.addEventListener("snapshot", (e) => { try { onSnapshot && onSnapshot(JSON.parse(e.data)); } catch {} });
  es.addEventListener("heartbeat", () => { /* no-op; just keeps connection alive */ });
  es.onerror = (e) => onError && onError(e);
  return () => es.close();
}

// ---------------------------------------------------------------------------
// Web Push subscription helpers
// ---------------------------------------------------------------------------

export async function fetchVapidPublicKey() {
  const r = await fetch(`${BASE}/api/push/vapid-public-key`);
  if (!r.ok) throw new Error(`vapid-public-key ${r.status}`);
  return r.json();
}

export async function postPushSubscription(subscription) {
  const subJson = subscription.toJSON();
  const r = await fetch(`${BASE}/api/push/subscribe`, {
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
  const r = await fetch(`${BASE}/api/push/unsubscribe`, {
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

export async function postManualTradeIntent({ asset, venue, side, price, qty, note }) {
  const r = await fetch(`${BASE}/api/manual-trade-intent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ asset, venue, side, price, qty, note: note || "" }),
  });
  if (!r.ok) throw new Error(`manual-trade-intent ${r.status}`);
  return r.json();
}
