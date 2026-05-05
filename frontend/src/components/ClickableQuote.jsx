import React, { useState, useEffect, useRef } from "react";
import OrderTicketModal from "./OrderTicketModal.jsx";
import { useTapePulse } from "../useTapePulse.js";

function fmtPrice(p) {
  if (!p) return "—";
  if (p >= 1000) return "$" + p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 1)    return "$" + p.toFixed(4);
  return "$" + p.toFixed(6);
}

const FLASH_MS = 350;   // how long each cell flashes after a hit

/**
 * Two big tappable cells — one per side. Whole cell is the click target
 * so you don't have to land on the digits.
 *
 * Visual states:
 *   - Static red text on the side that was last hit (lastAggressor prop)
 *   - Brief background-flash on every new aggressor hit detected on the
 *     1Hz tape feed (drives the "this is moving right now" feel)
 *   - Click → opens OrderTicketModal pre-filled with side + price
 *
 * If `disablePulse` is true (e.g. on a static historical signal card),
 * skip the live tape subscription and use only the prop-driven static
 * red flash.
 */
export default function ClickableQuote({
  asset, venue, bid, ask, lastAggressor,
  onSubmitted,
  size = "md",
  disablePulse = false,
}) {
  const [open, setOpen] = useState(null);
  const pulse = useTapePulse(disablePulse ? null : asset, disablePulse ? null : venue);
  // Live values from tape override props if present (so the cell shows
  // whatever's most current). Falls back to props if tape hasn't loaded
  // yet or if the component is in static mode.
  const liveBid = (!disablePulse && pulse.latestBid) || bid || 0;
  const liveAsk = (!disablePulse && pulse.latestAsk) || ask || 0;

  // Per-cell flash: useEffect on pulse counters triggers a 350ms class.
  const [flashBid, setFlashBid] = useState(false);
  const [flashAsk, setFlashAsk] = useState(false);
  const bidTimer = useRef(null);
  const askTimer = useRef(null);
  useEffect(() => {
    if (disablePulse || pulse.sellPulse === 0) return;
    setFlashBid(true);
    clearTimeout(bidTimer.current);
    bidTimer.current = setTimeout(() => setFlashBid(false), FLASH_MS);
  }, [pulse.sellPulse, disablePulse]);
  useEffect(() => {
    if (disablePulse || pulse.buyPulse === 0) return;
    setFlashAsk(true);
    clearTimeout(askTimer.current);
    askTimer.current = setTimeout(() => setFlashAsk(false), FLASH_MS);
  }, [pulse.buyPulse, disablePulse]);
  useEffect(() => () => {
    clearTimeout(bidTimer.current);
    clearTimeout(askTimer.current);
  }, []);

  const askStaticRed = lastAggressor === "buy";
  const bidStaticRed = lastAggressor === "sell";

  const sizeClasses = {
    sm: "py-2 px-3 text-base",
    md: "py-3 px-4 text-lg",
    lg: "py-5 px-6 text-2xl",
  }[size] || "py-3 px-4 text-lg";

  return (
    <>
      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => liveBid && setOpen({ side: "sell", price: liveBid })}
          disabled={!liveBid}
          className={`group rounded border ${flashBid ? "border-rose-400 ring-2 ring-rose-400/60" : "border-emerald-800"}
                       ${flashBid ? "bg-rose-900/50" : "bg-emerald-950/60"}
                       hover:bg-emerald-900/70 active:bg-emerald-800/70
                       disabled:opacity-40 disabled:cursor-not-allowed
                       ${sizeClasses} text-left transition-colors duration-200`}
        >
          <div className="text-[10px] uppercase tracking-wider text-emerald-300/80">
            Sell · hit the bid
          </div>
          <div className={`font-mono mt-1 transition-colors duration-200
                            ${flashBid ? "text-rose-200" : (bidStaticRed ? "text-rose-400 font-bold" : "text-slate-100")}`}>
            {fmtPrice(liveBid)}
          </div>
        </button>

        <button
          type="button"
          onClick={() => liveAsk && setOpen({ side: "buy", price: liveAsk })}
          disabled={!liveAsk}
          className={`group rounded border ${flashAsk ? "border-rose-400 ring-2 ring-rose-400/60" : "border-rose-800"}
                       ${flashAsk ? "bg-rose-900/50" : "bg-rose-950/60"}
                       hover:bg-rose-900/70 active:bg-rose-800/70
                       disabled:opacity-40 disabled:cursor-not-allowed
                       ${sizeClasses} text-left transition-colors duration-200`}
        >
          <div className="text-[10px] uppercase tracking-wider text-rose-300/80">
            Buy · lift the offer
          </div>
          <div className={`font-mono mt-1 transition-colors duration-200
                            ${flashAsk ? "text-rose-200" : (askStaticRed ? "text-rose-400 font-bold" : "text-slate-100")}`}>
            {fmtPrice(liveAsk)}
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
