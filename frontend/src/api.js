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

/** Web Push: fetch the server's VAPID public key (and whether push is configured). */
export async function fetchVapidPublicKey() {
  const r = await fetch(`${BASE}/api/push/vapid-public-key`);
  if (!r.ok) throw new Error(`vapid key ${r.status}`);
  return r.json();   // { public_key, configured }
}

/** Web Push: register a browser push subscription with the backend. */
export async function subscribePush(body) {
  const r = await fetch(`${BASE}/api/push/subscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`push subscribe ${r.status}`);
  return r.json();
}

/** Web Push: remove a browser push subscription from the backend. */
export async function unsubscribePush(body) {
  const r = await fetch(`${BASE}/api/push/unsubscribe`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`push unsubscribe ${r.status}`);
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
