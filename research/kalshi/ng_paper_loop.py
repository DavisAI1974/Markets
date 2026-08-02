#!/usr/bin/env python3
"""ng_paper_loop.py - G2 of the paper-trading dock (S110): the DAILY PAPER LOOP skeleton.

THE SHAPE (two-coach doctrine: this is the KALSHI DAILY COACH in shadow mode):
  morning:  the coach session builds the day state + emits paper/forecast_today.json
            {date, market_ticker, direction, day_move_usd_p50, band_usd, confidence, note}
  intraday: this loop turns the forecast into ORDER INTENTS, prices them off a LIVE PUBLIC quote
            snapshot, and places PAPER fills via kalshi_paper_ledger (caps enforced there).
  EOD:      settle() against the market's settlement value (expiration_value - the S99-verified
            settle print), score the day per-event, append to the batch record.

STRUCTURAL FACT (measured S100, recorded in PLANT_MAP.md): the live GLBX gateway needs raw TCP and
runs only from an AWS box - but PAPER trading needs only Kalshi's public HTTPS market data, so THIS
loop runs fine from the session environment. The box becomes necessary at the latency-critical live
stage, not the paper stage.

WHAT IS REAL vs STUBBED in v1 (honest inventory):
  REAL: quote fetch (Kalshi public API), sizing-under-caps, paper fills/fees/settle (ledger),
        per-event day log, batch-record append.
  STUBBED pending G0/coach-wiring: forecast_today.json is written by hand or by the coach session
        (no auto-spawn here); auto-settle needs the settled-market lookup wired for the day's
        specific event ticker (v1 takes --settle-value from the operator reading the print).

USAGE
  python ng_paper_loop.py quote   --ticker KXNATGASD-26AUG04            (print the live quote)
  python ng_paper_loop.py trade                                         (read forecast_today.json,
                                                                         place the paper order)
  python ng_paper_loop.py eod     --settle-value 1                      (settle + day log)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kalshi_paper_ledger as ledger  # noqa: E402
import batch_record  # noqa: E402

PAPER = os.path.join(HERE, "paper")
FORECAST = os.path.join(PAPER, "forecast_today.json")
API = "https://api.elections.kalshi.com/trade-api/v2"

# SIZING POLICY v1 (deliberately blunt; the dock test is plumbing, not edge):
# confidence high -> 20 contracts, med -> 10, low -> 0 (stand down). Direction long-YES only when
# the forecast day-move sign agrees with the bracket being bought; the coach picks the bracket.
SIZE_BY_CONF = {"high": 20, "med": 10, "low": 0}


def fetch_market(ticker: str) -> dict:
    """Public market data - no auth. Returns the market object (yes_bid/yes_ask in cents)."""
    url = f"{API}/markets/{ticker}"
    with urllib.request.urlopen(url, timeout=20) as r:
        data = json.loads(r.read().decode())
    m = data.get("market") or data
    return m


def quote_from_market(m: dict) -> dict:
    bid_c, ask_c = m.get("yes_bid"), m.get("yes_ask")
    return {"ticker": m.get("ticker"), "yes_bid": (bid_c or 0) / 100.0,
            "yes_ask": (ask_c or 0) / 100.0, "status": m.get("status"),
            "close_time": m.get("close_time"), "source": "kalshi_public_api"}


def cmd_quote(ticker: str) -> int:
    q = quote_from_market(fetch_market(ticker))
    print(json.dumps(q, indent=1))
    return 0


def cmd_trade() -> int:
    if not os.path.exists(FORECAST):
        print(f"[paper-loop] no {os.path.relpath(FORECAST, HERE)} - the coach session writes it "
              f"(date, market_ticker, direction, day_move_usd_p50, band_usd, confidence, note).")
        return 1
    f = json.load(open(FORECAST, encoding="utf-8"))
    size = SIZE_BY_CONF.get(str(f.get("confidence", "low")).lower(), 0)
    if size == 0:
        ev = batch_record.append("paper", "note", f"paper loop STOOD DOWN (confidence "
                                 f"{f.get('confidence')}) for {f.get('date')}")
        print("[paper-loop] stand-down recorded:", json.dumps(ev))
        return 0
    q = quote_from_market(fetch_market(f["market_ticker"]))
    side = "yes" if str(f.get("direction", "")).lower() in ("up", "yes", "long") else "no"
    # taker at the offered price; the ledger enforces every cap and records rejects
    res = ledger.place(market=f["market_ticker"], side=side, count=size,
                       limit=q["yes_ask"] if side == "yes" else round(1 - q["yes_bid"], 4),
                       bid=q["yes_bid"], ask=q["yes_ask"], quote_source=q["source"],
                       note=f"paper-loop {f.get('date')} p50 {f.get('day_move_usd_p50')} "
                            f"band {f.get('band_usd')} conf {f.get('confidence')}")
    print("[paper-loop]", json.dumps(res))
    batch_record.append("paper", "note", f"paper order {res['type']} {f['market_ticker']} "
                        f"{side} x{size} @ {res.get('price', res.get('limit'))}")
    return 0


def cmd_eod(settle_value: int) -> int:
    if not os.path.exists(FORECAST):
        print("[paper-loop] no forecast_today.json to settle against")
        return 1
    f = json.load(open(FORECAST, encoding="utf-8"))
    res = ledger.settle(f["market_ticker"], settle_value)
    print("[paper-loop]", json.dumps(res))
    ledger.status()
    batch_record.append("paper", "scored", f"{f.get('date')} settle {settle_value} -> "
                        f"realized {res.get('realized_pnl_usd')} on {f['market_ticker']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("quote"); q.add_argument("--ticker", required=True)
    sub.add_parser("trade")
    e = sub.add_parser("eod"); e.add_argument("--settle-value", type=int, required=True)
    a = ap.parse_args()
    if a.cmd == "quote":
        return cmd_quote(a.ticker)
    if a.cmd == "trade":
        return cmd_trade()
    return cmd_eod(a.settle_value)


if __name__ == "__main__":
    raise SystemExit(main())
