import React, { useState, useEffect } from "react";
import { postManualTradeIntent } from "../api.js";
import { useStore } from "../store.js";

function fmtPrice(p) {
  if (!p) return "—";
  if (p >= 1000) return "$" + p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 1)    return "$" + p.toFixed(4);
  return "$" + p.toFixed(6);
}

const QTY_KEY = "marketsWatch.lastQty";   // remember last qty between clicks

/**
 * Order ticket: confirm + submit. Pre-filled with side + price from the
 * click. Side is locked, price is locked (the user already chose by
 * clicking a side); user picks size and confirms.
 *
 * Submit POSTs to /api/manual-trade-intent which records an audit-trail
 * entry on the backend. Real-money execution stays with the user's own
 * exchange / executor — this UI never holds private keys, and the central
 * host never holds capital. It just records the human's intent for
 * audit purposes; the user then executes on their exchange of choice
 * (or wires their local executor to the audit feed).
 */
export default function OrderTicketModal({ asset, venue, side, price, onClose, onSubmitted }) {
  const practiceMode = useStore((s) => s.practiceMode);
  const setPracticeMode = useStore((s) => s.setPracticeMode);
  const [qty, setQty] = useState(() => {
    const stored = localStorage.getItem(`${QTY_KEY}.${asset}`);
    return stored ? parseFloat(stored) : 0.1;
  });
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(null);     // null | { ok, signal_id?, error }
  const [note, setNote] = useState("");
  const [confirmedLive, setConfirmedLive] = useState(false);  // double-confirm for live

  useEffect(() => {
    function onKey(e) { if (e.key === "Escape" && !submitting) onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, submitting]);

  const sideLabel = side === "buy" ? "BUY · lift the offer" : "SELL · hit the bid";
  const sideColor = side === "buy" ? "bg-rose-700 hover:bg-rose-600" : "bg-emerald-700 hover:bg-emerald-600";
  const notional = (qty * price) || 0;

  async function submit() {
    setSubmitting(true);
    setDone(null);
    try {
      localStorage.setItem(`${QTY_KEY}.${asset}`, String(qty));
      const r = await postManualTradeIntent({
        asset, venue, side, price, qty, note,
        practice: practiceMode,
      });
      setDone({ ok: true, intent_id: r.intent_id, practice: practiceMode, fill_price: r.fill_price });
      onSubmitted && onSubmitted(r);
    } catch (e) {
      setDone({ ok: false, error: String(e) });
    }
    setSubmitting(false);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={(e) => e.target === e.currentTarget && !submitting && onClose()}
    >
      <div className={`bg-slate-900 border rounded-t-lg sm:rounded-lg w-full max-w-md p-4 shadow-2xl
                         ${practiceMode ? "border-sky-700" : "border-amber-600"}`}>
        {/* Mode banner — prominent so the user always knows what's at stake */}
        <div className={`flex items-center justify-between rounded px-3 py-2 mb-3 text-xs font-bold
                           ${practiceMode
                             ? "bg-sky-950/60 border border-sky-700 text-sky-200"
                             : "bg-amber-950/60 border border-amber-700 text-amber-200"}`}>
          <span>
            {practiceMode
              ? "🎯 PRACTICE — simulated fill, no real money"
              : "⚠️ LIVE — real money on your exchange"}
          </span>
          <button
            onClick={() => { setPracticeMode(!practiceMode); setConfirmedLive(false); }}
            disabled={submitting}
            className={`rounded px-2 py-0.5 text-[10px] uppercase tracking-wide
                          ${practiceMode
                            ? "bg-sky-700 hover:bg-sky-600 text-white"
                            : "bg-amber-700 hover:bg-amber-600 text-white"} disabled:opacity-40`}
          >
            switch to {practiceMode ? "live" : "practice"}
          </button>
        </div>

        {/* Header */}
        <div className="flex items-baseline justify-between mb-3">
          <div>
            <div className={`inline-block px-2 py-0.5 rounded text-xs font-bold text-white ${sideColor}`}>
              {sideLabel}
            </div>
            <div className="font-mono text-base font-semibold text-slate-100 mt-1">
              {asset}-USD <span className="text-slate-400 text-sm">on {venue}</span>
            </div>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-100 text-xl px-1" aria-label="close">×</button>
        </div>

        {/* Locked price + size input */}
        <div className="grid grid-cols-2 gap-2 mb-3">
          <div className="bg-slate-950 rounded px-2 py-2">
            <div className="text-[10px] uppercase tracking-wide text-slate-500">Price (locked)</div>
            <div className="font-mono text-lg text-slate-100 mt-1">{fmtPrice(price)}</div>
          </div>
          <div className="bg-slate-950 rounded px-2 py-2">
            <label className="text-[10px] uppercase tracking-wide text-slate-500 block">
              Size ({asset})
            </label>
            <input
              type="number"
              step="0.001"
              min="0"
              autoFocus
              value={qty}
              onChange={(e) => setQty(parseFloat(e.target.value) || 0)}
              className="w-full bg-transparent border-b border-slate-700 focus:border-slate-400 outline-none font-mono text-lg text-slate-100 mt-1"
            />
          </div>
        </div>

        {/* Notional preview */}
        <div className="bg-slate-950 rounded px-2 py-2 mb-3 text-xs">
          <div className="flex justify-between">
            <span className="text-slate-400">Notional</span>
            <span className="font-mono text-slate-100">{fmtPrice(notional)}</span>
          </div>
        </div>

        {/* Optional note */}
        <input
          type="text"
          placeholder="Note (optional, e.g. 'fading the cascade')"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          className="w-full bg-slate-950 border border-slate-700 rounded px-2 py-2 text-xs text-slate-200 mb-3 outline-none focus:border-slate-500"
          maxLength={200}
        />

        {/* Disclaimer — different for practice vs live */}
        <p className="text-[10px] text-slate-500 mb-3 leading-relaxed">
          {practiceMode
            ? <>Practice mode simulates a fill against the current bid/ask with a 25 bp fee.
                The trade tracks against live prices; close it from the Practice tab to see
                realized P&L. No real money. Use this to learn the workflow.</>
            : <>Live mode records the intent and emits it on the SSE stream so your local
                executor (with your exchange API keys) can place the order on your wallet.
                The central app never holds your keys. Make sure your executor is running
                before you confirm.</>}
        </p>

        {/* Live-mode double-confirm checkbox */}
        {!practiceMode && !done?.ok && (
          <label className="flex items-start gap-2 text-xs text-amber-200 mb-3">
            <input
              type="checkbox"
              checked={confirmedLive}
              onChange={(e) => setConfirmedLive(e.target.checked)}
              className="mt-0.5"
            />
            <span>
              I understand this places a <strong>real order</strong> on my exchange,
              and my executor is running locally with my API keys.
            </span>
          </label>
        )}

        {/* Result banner */}
        {done && (
          <div className={`text-xs rounded px-2 py-2 mb-3 ${
            done.ok
              ? (done.practice
                  ? "bg-sky-950/60 border border-sky-700 text-sky-200"
                  : "bg-emerald-950/60 border border-emerald-800 text-emerald-200")
              : "bg-rose-950/60 border border-rose-800 text-rose-200"
          }`}>
            {done.ok
              ? (done.practice
                  ? <>Practice fill at <code className="font-mono">${done.fill_price?.toFixed?.(4) ?? "—"}</code>.
                      Open in the Practice tab to track + close.</>
                  : <>Live intent recorded. Intent id <code className="font-mono">{done.intent_id}</code>.
                      Your executor will pick it up off the SSE stream.</>)
              : <>Error: {done.error}</>}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={submitting}
            className="flex-1 rounded bg-slate-800 hover:bg-slate-700 px-3 py-2 text-sm text-slate-200 disabled:opacity-40"
          >
            {done?.ok ? "Close" : "Cancel"}
          </button>
          {!done?.ok && (
            <button
              type="button"
              onClick={submit}
              disabled={submitting || !qty || qty <= 0 || (!practiceMode && !confirmedLive)}
              className={`flex-1 rounded px-3 py-2 text-sm font-semibold text-white disabled:opacity-40
                            ${practiceMode
                              ? "bg-sky-700 hover:bg-sky-600"
                              : sideColor}`}
            >
              {submitting
                ? "Submitting…"
                : practiceMode
                  ? `Practice ${side === "buy" ? "BUY" : "SELL"} ${qty} ${asset}`
                  : `LIVE ${side === "buy" ? "BUY" : "SELL"} ${qty} ${asset}`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
