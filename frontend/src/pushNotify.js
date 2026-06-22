/**
 * pushNotify.js — browser-side Web Push enable/disable helpers.
 *
 * The backend (backend/push.py + /api/push/* endpoints) and the service
 * worker (public/service-worker.js, which already has a `push` handler) are
 * done. This module is the missing glue: ask permission, subscribe via the
 * PushManager using the server's VAPID public key, and register/unregister
 * the subscription with the backend.
 *
 * All paths degrade gracefully: unsupported browsers, denied permission, and
 * a server that has no VAPID key configured each return a clear state rather
 * than throwing into the UI.
 */

import { fetchVapidPublicKey, subscribePush, unsubscribePush } from "./api.js";

/** VAPID public keys are urlsafe-base64; PushManager needs a Uint8Array. */
function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export function isPushSupported() {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

/**
 * Current push state, for rendering a toggle.
 * @returns {Promise<{supported:boolean, permission:string, subscribed:boolean,
 *                     serverConfigured:boolean}>}
 */
export async function getPushState() {
  if (!isPushSupported()) {
    return { supported: false, permission: "unsupported", subscribed: false, serverConfigured: false };
  }
  let serverConfigured = false;
  try {
    const { configured } = await fetchVapidPublicKey();
    serverConfigured = !!configured;
  } catch {
    serverConfigured = false;
  }
  let subscribed = false;
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    subscribed = !!sub;
  } catch {
    subscribed = false;
  }
  return { supported: true, permission: Notification.permission, subscribed, serverConfigured };
}

/**
 * Request permission, subscribe, and register with the backend.
 * Throws an Error with a user-readable message on any failure.
 */
export async function enablePush() {
  if (!isPushSupported()) throw new Error("This browser doesn't support push notifications.");

  const { public_key, configured } = await fetchVapidPublicKey();
  if (!configured || !public_key) {
    throw new Error("Push isn't configured on the server yet (no VAPID key).");
  }

  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    throw new Error(
      permission === "denied"
        ? "Notifications are blocked. Enable them in your browser/site settings."
        : "Notification permission was not granted.",
    );
  }

  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(public_key),
    });
  }

  const j = sub.toJSON();
  await subscribePush({
    endpoint: j.endpoint,
    p256dh: j.keys?.p256dh || "",
    auth: j.keys?.auth || "",
    user_agent: navigator.userAgent || "",
  });
  return true;
}

/** Unsubscribe locally and tell the backend to drop the subscription. */
export async function disablePush() {
  if (!isPushSupported()) return false;
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.getSubscription();
  if (!sub) return false;

  const j = sub.toJSON();
  // Tell the backend first so a failed local unsubscribe doesn't leave a stale
  // server entry; backend only keys on endpoint, but the body schema needs keys.
  try {
    await unsubscribePush({
      endpoint: j.endpoint,
      p256dh: j.keys?.p256dh || "",
      auth: j.keys?.auth || "",
      user_agent: navigator.userAgent || "",
    });
  } catch {
    /* best-effort; still unsubscribe locally below */
  }
  await sub.unsubscribe();
  return true;
}
