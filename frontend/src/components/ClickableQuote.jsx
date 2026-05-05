import React, { useState } from "react";
import OrderTicketModal from "./OrderTicketModal.jsx";

function fmtPrice(p) {
  if (!p) return "—";
  if (p >= 1000) return "$" + p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 1)    return "$" + p.toFixed(4);
  return "$" + p.toFixed(6);
}

/**
 * Two big tappable boxes — bid (sell here) and ask (buy here).
 * The whole box is clickable so you don't have to land your cursor on
 * the digits. On tap, opens an order-ticket modal pre-filled with
 * side + price.
 *
 * Color: whichever side was last hit by a trade (props.lastAggressor)
 * gets red text + bold; the other side stays default. This matches
 * standard tape-side flash for level-1 quote displays.
 */
export default function ClickableQuote({
  asset, venue, bid, ask, lastAggressor,
  onSubmitted,                 // optional callback after a manual-trade intent is recorded
  size = "md",                 // "sm" | "md" | "lg"
}) {
  const [open, setOpen] = useState(null);   // null | { side, price }

  const askFlash = lastAggressor === "buy";   // last trade lifted the ask
  const bidFlash = lastAggressor === "sell";  // last trade hit the bid

  const sizeClasses = {
    sm: "py-2 px-3 text-base",
    md: "py-3 px-4 text-lg",
    lg: "py-5 px-6 text-2xl",
  }[size] || "py-3 px-4 text-lg";

  function clickBid() {
    if (!bid) return;
    setOpen({ side: "sell", price: bid });
  }
  function clickAsk() {
    if (!ask) return;
    setOpen({ side: "buy", price: ask });
  }

  return (
    <>
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={clickBid}
          disabled={!bid}
          className={`group rounded border border-emerald-800 bg-emerald-950/60
                       hover:bg-emerald-900/70 active:bg-emerald-800/70
                       disabled:opacity-40 disabled:cursor-not-allowed
                       ${sizeClasses} text-left transition`}
        >
          <div className="text-[10px] uppercase tracking-wider text-emerald-300/80">
            Sell · hit the bid
          </div>
          <div className={`font-mono mt-1 ${bidFlash ? "text-rose-400 font-bold" : "text-slate-100"}`}>
            {fmtPrice(bid)}
          </div>
        </button>

        <button
          type="button"
          onClick={clickAsk}
          disabled={!ask}
          className={`group rounded border border-rose-800 bg-rose-950/60
                       hover:bg-rose-900/70 active:bg-rose-800/70
                       disabled:opacity-40 disabled:cursor-not-allowed
                       ${sizeClasses} text-left transition`}
        >
          <div className="text-[10px] uppercase tracking-wider text-rose-300/80">
            Buy · lift the offer
          </div>
          <div className={`font-mono mt-1 ${askFlash ? "text-rose-400 font-bold" : "text-slate-100"}`}>
            {fmtPrice(ask)}
          </div>
        </button>
      </div>
      {open && (
        <OrderTicketModal
          asset={asset}
          venue={venue}
          side={open.side}
          price={open.price}
          onClose={() => setOpen(null)}
          onSubmitted={onSubmitted}
        />
      )}
    </>
  );
}
