import React, { useEffect, useState } from "react";
import { getPushState, enablePush, disablePush } from "../pushNotify.js";

/**
 * A self-contained "Notify me" control for high-confidence signal pushes.
 * Reflects current state (supported / permission / subscribed / server-config)
 * and handles enable + disable. Safe to drop anywhere.
 */
export default function NotifyToggle() {
  const [state, setState] = useState(null);   // null = loading
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function refresh() {
    try {
      setState(await getPushState());
    } catch {
      setState({ supported: false, permission: "unsupported", subscribed: false, serverConfigured: false });
    }
  }

  useEffect(() => { refresh(); }, []);

  async function onEnable() {
    setBusy(true); setMsg("");
    try {
      await enablePush();
      setMsg("Notifications on. You'll get a push on high-confidence signals.");
    } catch (e) {
      setMsg(e?.message || "Couldn't enable notifications.");
    } finally {
      setBusy(false);
      refresh();
    }
  }

  async function onDisable() {
    setBusy(true); setMsg("");
    try {
      await disablePush();
      setMsg("Notifications off.");
    } catch (e) {
      setMsg(e?.message || "Couldn't disable notifications.");
    } finally {
      setBusy(false);
      refresh();
    }
  }

  if (state === null) {
    return <p className="text-sm text-slate-500">Checking notification support…</p>;
  }

  if (!state.supported) {
    return (
      <p className="text-sm text-slate-400">
        This browser doesn't support push notifications. On iOS, add the app to your Home Screen
        first, then re-open it.
      </p>
    );
  }

  if (!state.serverConfigured) {
    return (
      <p className="text-sm text-slate-400">
        Push notifications aren't switched on for this server yet. (No VAPID key configured.)
      </p>
    );
  }

  const blocked = state.permission === "denied";

  return (
    <div className="text-sm">
      <div className="flex items-center gap-3">
        {state.subscribed ? (
          <button
            onClick={onDisable}
            disabled={busy}
            className="px-3 py-1.5 rounded bg-slate-800 text-slate-100 border border-slate-700 hover:bg-slate-700 disabled:opacity-50"
          >
            {busy ? "Working…" : "Turn off notifications"}
          </button>
        ) : (
          <button
            onClick={onEnable}
            disabled={busy || blocked}
            className="px-3 py-1.5 rounded bg-blue-700 text-white hover:bg-blue-600 disabled:opacity-50"
          >
            {busy ? "Working…" : "Notify me on strong signals"}
          </button>
        )}
        <span
          className={`inline-block w-2 h-2 rounded-full ${state.subscribed ? "bg-green-500" : "bg-slate-600"}`}
          title={state.subscribed ? "Subscribed" : "Not subscribed"}
        />
      </div>
      {blocked && !state.subscribed && (
        <p className="text-xs text-yellow-400/80 mt-2">
          Notifications are blocked for this site. Enable them in your browser/site settings, then reload.
        </p>
      )}
      {msg && <p className="text-xs text-slate-400 mt-2">{msg}</p>}
    </div>
  );
}
