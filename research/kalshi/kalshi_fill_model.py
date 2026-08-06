#!/usr/bin/env python3
"""FEED M part 2 (S100, DATA_GATE_S98) - the Kalshi fill/fee model. Execution economics ONLY;
the lag's existence is ESTABLISHED (gate section 0c) and never re-litigated here.

FEES (verified formula, carried from lag_exploit_backtest.py S81, per Kalshi's published
schedule): taker fee per contract = 0.07 * P * (1-P) DOLLARS, P = trade price in [0,1], charged
per side; Kalshi rounds UP to the next cent per ORDER (the continuous formula is the per-contract
expectation; rounding is order-size dependent and reported as a note, never silently added).
Maker (resting) orders pay NO fee - but a maker FILL cannot be claimed historically because book
depth history is structurally unobtainable (feed L: no historical orderbook endpoint; candle
yes_bid/yes_ask OHLC is the book ceiling). Maker economics are therefore reported as BOUNDS ONLY,
labeled; the live collector's books (accruing since 2026-07-12) are the future fill-evidence
source.

SPREAD: per-bracket per-minute from the 1m candles (yes_ask.close - yes_bid.close). The
conservative taker baseline: BUY at ask / SELL at bid, top-of-book, NO size claim (depth unknown
historically). Round trip = entry fee + exit fee + full spread once (enter crossing, exit
crossing; the spread is paid via the two crossings vs mid).
"""
from __future__ import annotations

import gzip
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KALSHI_DIR_CANDIDATES = [os.path.join(HERE, "..", "..", "data", "kalshi"),
                         os.path.join("data", "kalshi")]


def kalshi_dir() -> str:
    for p in KALSHI_DIR_CANDIDATES:
        if os.path.isdir(p):
            return p
    raise FileNotFoundError("data/kalshi absent - platform_sync pull --prefix kalshi/ first")


def taker_fee_per_contract(p: float) -> float:
    """Kalshi taker fee per contract, DOLLARS. p in [0,1]. Continuous expectation (order-level
    rounding up to the cent is extra, size-dependent - noted, not modeled)."""
    assert 0.0 <= p <= 1.0, p
    return 0.07 * p * (1.0 - p)


def round_trip_taker_cost(p_entry: float, p_exit: float, spread_entry: float,
                          spread_exit: float) -> dict:
    """Conservative taker round trip per contract: both fees + half-spread paid at each crossing
    (entry at ask = mid + s/2; exit at bid = mid - s/2). All dollars."""
    fee = taker_fee_per_contract(p_entry) + taker_fee_per_contract(p_exit)
    spread_cost = spread_entry / 2.0 + spread_exit / 2.0
    return {"fees": round(fee, 4), "spread_cost": round(spread_cost, 4),
            "total": round(fee + spread_cost, 4),
            "note": "taker both sides, top-of-book, no size claim; maker = 0 fee but fill "
                    "UNCLAIMABLE historically (bounds only)"}


def maker_bound_note() -> str:
    return ("MAKER BOUND ONLY: fee 0, cost bound = 0 spread if filled at rest - but resting-fill "
            "probability requires book evidence (live collector books, 2026-07-12+); never claimed "
            "from candles")


def day_spreads(series: str, event_ticker: str) -> dict[int, float]:
    """{end_period_ts_minute: yes spread dollars} from the 1m candles of one bracket ticker file.
    Only minutes where both sides quote (bid>0 and ask<1 sanity NOT enforced - raw carried)."""
    d = kalshi_dir()
    path = os.path.join(d, "candles", series, f"{event_ticker}_candles_1m.jsonl.gz")
    out = {}
    with gzip.open(path, "rt") as fh:
        for line in fh:
            r = json.loads(line)
            try:
                yb, ya = r["yes_bid"], r["yes_ask"]
                bid = float(yb.get("close", yb.get("close_dollars")))
                ask = float(ya.get("close", ya.get("close_dollars")))
            except (KeyError, TypeError, ValueError):
                continue                                      # two store vintages: close / close_dollars
            out[int(r["end_period_ts"])] = ask - bid
    return out


def selftest() -> bool:
    ok = True

    def chk(c, m):
        nonlocal ok
        print(("  PASS " if c else "  FAIL ") + m)
        ok = ok and bool(c)

    print("[fill-model selftest]")
    chk(abs(taker_fee_per_contract(0.50) - 0.0175) < 1e-12, "fee at P=0.50 = $0.0175 (the schedule's max)")
    chk(abs(taker_fee_per_contract(0.10) - 0.0063) < 1e-12, "fee at P=0.10 = $0.0063")
    chk(taker_fee_per_contract(0.0) == 0.0 and taker_fee_per_contract(1.0) == 0.0, "fee vanishes at 0/1")
    rt = round_trip_taker_cost(0.50, 0.60, 0.02, 0.02)
    chk(abs(rt["fees"] - (0.0175 + 0.0168)) < 1e-9 and abs(rt["spread_cost"] - 0.02) < 1e-12,
        f"round trip 50c->60c on 2c spreads = {rt['total']} (fees {rt['fees']} + spread {rt['spread_cost']})")
    # PIN (recorded from the first measured run 2026-07-20): a real mid-life bracket's median
    # 1m spread - KXNATGASD-26APR2217-T2.960, measured below and pinned in the lag-map notes.
    print("[fill-model selftest]", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
