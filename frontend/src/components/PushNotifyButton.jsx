import React, { useEffect, useState } from "react";
import {
  fetchVapidPublicKey,
  postPushSubscription,
  postPushUnsubscribe,
} from "../api.js";

// Convert URL-safe base64 (the format VAPID public keys arrive in) to a
// Uint8Array as required by pushManager.subscribe({ applicationServerKey }).
function urlB64ToUint8Array(b64) {
  const padding = "=".repeat((4 - (b64.length % 4)) % 4);
  const base64 = (b64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  const out = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

export default function PushNotifyButton() {
  const [state, setState] = useState("checking"); // checking | unsupported | not-configured | unsubscribed | subscribed | working | error
  const [error, setError] = useState("");
  const [permission, setPermission] = useState(
    typeof Notification !== "undefined" ? Notification.permission : "default"
  );

  useEffect(() => {
    (async () => {
      if (
        typeof window === "undefined"
        || !("serviceWorker" in navigator)
        || !("PushManager" in window)
        || typeof Notification === "undefined"
      ) {
        setState("unsupported");
        return;
      }
      try {
        const { configured } = await fetchVapidPublicKey();
        if (!configured) {
          setState("not-configured");
          return;
        }
        const reg = await navigator.serviceWorker.ready;
        const existing = await reg.pushManager.getSubscription();
        setState(existing ? "subscribed" : "unsubscribed");
      } catch (e) {
        setError(String(e));
        setState("error");
      }
    })();
  }, []);

  async function subscribe() {
    setState("working");
    setError("");
    try {
      const perm = await Notification.requestPermission();
      setPermission(perm);
      if (perm !== "granted") {
        setError(`Browser permission: ${perm}. Enable notifications in site settings.`);
        setState("unsubscribed");
        return;
      }
      const { public_key, configured } = await fetchVapidPublicKey();
      if (!configured) {
        setState("not-configured");
        return;
      }
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlB64ToUint8Array(public_key),
      });
      await postPushSubscription(sub);
      setState("subscribed");
    } catch (e) {
      setError(String(e));
      setState("error");
    }
  }

  async function unsubscribe() {
    setState("working");
    setError("");
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      if (sub) {
        await postPushUnsubscribe(sub.endpoint);
        await sub.unsubscribe();
      }
      setState("unsubscribed");
    } catch (e) {
      setError(String(e));
      setState("error");
    }
  }

  if (state === "checking") {
    return <p className="text-xs text-slate-500">Checking notification support…</p>;
  }
  if (state === "unsupported") {
    return (
      <div className="text-xs text-slate-500">
        Push notifications aren't supported in this browser. On iPhone, install
        the app first via Share → Add to Home Screen, then open it from the
        home screen and re-try.
      </div>
    );
  }
  if (state === "not-configured") {
    return (
      <div className="text-xs text-slate-500">
        Push notifications aren't configured on the backend yet (VAPID keys
        not set). Once your admin wires <code>VAPID_PRIVATE_KEY</code> in
        the backend env, this button will activate.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {state === "subscribed" ? (
          <button
            onClick={unsubscribe}
            className="text-xs rounded px-3 py-2 bg-slate-700 hover:bg-slate-600 text-slate-100 font-medium"
          >
            Notifications ON — tap to disable
          </button>
        ) : (
          <button
            onClick={subscribe}
            disabled={state === "working"}
            className="text-xs rounded px-3 py-2 bg-emerald-700 hover:bg-emerald-600 text-emerald-50 font-medium disabled:opacity-50"
          >
            {state === "working" ? "Working…" : "Notify me on new signals"}
          </button>
        )}
        <span className="text-[10px] text-slate-500">
          permission: <code>{permission}</code>; status: <code>{state}</code>
        </span>
      </div>
      {error ? (
        <p className="text-xs text-rose-400 break-all">{error}</p>
      ) : null}
    </div>
  );
}
