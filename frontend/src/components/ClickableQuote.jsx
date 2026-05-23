import React, { useState, useEffect, useRef } from "react";
import OrderTicketModal from "./OrderTicketModal.jsx";
import { useTapePulse } from "../useTapePulse.js";

function fmtPrice(p) {
  if (!p) return "—";
  if (p >= 1000) return p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  if (p >= 1)    return p.toFixed(4);
  return p.toFixed(6);
}

function fmtQty(q) {
  if (q == null) return "—";
  if (q >= 1000) return q.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (q >= 1)    return q.toFixed(3);
  return q.toFixed(6);
}

const FLASH_MS = 350;   // locked: 350ms ease-out red

/**
 * Two centered "Bid" / "Ask" tape-style cells. Tap target is the whole cell.
 *
 * Flash semantic (LOCKED, industry standard):
 *   - buy aggressor  → ASK flashes red (the offer just got lifted)
 *   - sell aggressor → BID flashes red (the bid just got hit)
 *
 * Persistent prop-driven flash (lastAggressor) for static contexts, plus
 * live 1Hz pulse via useTapePulse for the tape page. disablePulse skips the
 * subscription for static historical contexts.
 *
 * Optional bidVolume / askVolume render in the per-side volume slot (e.g.
 * "1m vol 1.604 BTC"); the chart payload doesn't include top-of-book size,
 * so this slot reflects recent-minute traded volume on that side instead.
 */
export default function ClickableQuote({
  asset, venue, bid, ask, lastAggressor,
  bidVolume, askVolume, volumeLabel = "1m vol",
  asset_symbol,
  onSubmitted,
  disablePulse = false,
  tradeOption = null,
}) {
  const [open, setOpen] = useState(null);
  const pulse = useTapePulse(disablePulse ? null : asset, disablePulse ? null : venue);
  const liveBid = (!disablePulse && pulse.latestBid) || bid || 0;
  const liveAsk = (!disablePulse && pulse.latestAsk) || ask || 0;

  // Per-cell flash counters (350ms each)
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
  const askRed = flashAsk || askStaticRed;
  const bidRed = flashBid || bidStaticRed;

  const sym = asset_symbol || asset;
  const optionState = tradeOption?.trade_option_state || "";
  const optionSide = tradeOption?.trade_option_side || "";
  const optionTradable = optionState === "early_probe" || optionState === "confirmed";
  const optionPrice = optionSide === "buy" ? liveAsk : optionSide === "sell" ? liveBid : 0;
  const optionTone = optionState === "early_probe"
    ? "border-amber-700 bg-amber-950/30 text-amber-100"
    : "border-emerald-700 bg-emerald-950/30 text-emerald-100";
  const optionNote = tradeOption?.trade_option_label
    ? `${tradeOption.trade_option_label}; ${tradeOption.trade_option_size_hint || ""}`
    : "";

  return (
    <>
      <div className="grid grid-cols-2 gap-0.5 bg-slate-800 rounded-lg overflow-hidden">
        <button
          type="button"
          onClick={() => liveBid && setOpen({ side: "sell", price: liveBid })}
          disabled={!liveBid}
          className={`bg-slate-900 px-3 pt-3.5 pb-3 text-center cursor-pointer
                      hover:bg-slate-800 active:bg-slate-700
                      disabled:opacity-40 disabled:cursor-not-allowed
                      transition-colors duration-200
                      ${flashBid ? "ring-1 ring-rose-500/50" : ""}`}
        >
          <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1.5">Bid</div>
          <div className={`font-mono text-[21px] font-semibold transition-colors duration-200
                            ${bidRed ? "text-rose-400" : "text-slate-100"}`}>
            {fmtPrice(liveBid)}
          </div>
          {bidVolume != null && (
            <div className="font-mono text-[11px] text-slate-400 mt-1">{volumeLabel} {fmtQty(bidVolume)} {sym}</div>
          )}
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-1.5">tap to sell</div>
        </button>

        <button
          type="button"
          onClick={() => liveAsk && setOpen({ side: "buy", price: liveAsk })}
          disabled={!liveAsk}
          className={`bg-slate-900 px-3 pt-3.5 pb-3 text-center cursor-pointer
                      hover:bg-slate-800 active:bg-slate-700
                      disabled:opacity-40 disabled:cursor-not-allowed
                      transition-colors duration-200
                      ${flashAsk ? "ring-1 ring-rose-500/50" : ""}`}
        >
          <div className="text-[10px] uppercase tracking-widest text-slate-500 font-bold mb-1.5">Ask</div>
          <div className={`font-mono text-[21px] font-semibold transition-colors duration-200
                            ${askRed ? "text-rose-400" : "text-slate-100"}`}>
            {fmtPrice(liveAsk)}
          </div>
          {askVolume != null && (
            <div className="font-mono text-[11px] text-slate-400 mt-1">{volumeLabel} {fmtQty(askVolume)} {sym}</div>
          )}
          <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-1.5">tap to buy</div>
        </button>
      </div>
      {optionTradable && (
        <div className={`mt-2 rounded border px-2.5 py-2 text-xs ${optionTone}`}>
          <div className="flex items-center justify-between gap-2">
            <div>
              <div className="font-semibold">{tradeOption.trade_option_label}</div>
              <div className="opacity-80">
                {tradeOption.trade_option_size_hint} · readiness {tradeOption.trade_option_readiness}/100
              </div>
            </div>
            <button
              type="button"
              disabled={!optionPrice}
              onClick={() => optionPrice && setOpen({ side: optionSide, price: optionPrice, note: optionNote })}
              className="rounded bg-slate-100 px-2.5 py-1.5 text-[11px] font-semibold text-slate-950 hover:bg-white disabled:opacity-40"
            >
              Open {optionState === "early_probe" ? "probe" : "trade"}
            </button>
          </div>
        </div>
      )}
      {open && (
        <OrderTicketModal
          asset={asset}
          venue={venue}
          side={open.side}
          price={open.price}
          initialNote={open.note || ""}
          tradeOption={tradeOption}
          onClose={() => setOpen(null)}
          onSubmitted={onSubmitted}
        />
      )}
    </>
  );
}
