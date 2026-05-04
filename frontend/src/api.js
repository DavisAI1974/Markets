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

/** Subscribe to SSE stream. Returns a cleanup fn. */
export function subscribeToStream({ onSignal, onSnapshot, onError }) {
  const es = new EventSource(`${BASE}/api/stream`);
  es.addEventListener("signal", (e) => { try { onSignal && onSignal(JSON.parse(e.data)); } catch {} });
  es.addEventListener("snapshot", (e) => { try { onSnapshot && onSnapshot(JSON.parse(e.data)); } catch {} });
  es.addEventListener("heartbeat", () => { /* no-op; just keeps connection alive */ });
  es.onerror = (e) => onError && onError(e);
  return () => es.close();
}
