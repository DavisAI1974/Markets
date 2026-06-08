"""Tests for the Bybit USDT-perp mm_passive extensions to forward_paper.py
(Phase 2, QUOTE_SERVICE_PLAN.md). Per-cell maker fee, perp funding term,
mm_passive round-trip spread capture, and spot-cell backward compatibility.

Runnable two ways:
    python -m pytest tests/test_forward_paper_mm.py
    python tests/test_forward_paper_mm.py   # standalone, no pytest needed
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from forward_paper import (  # noqa: E402
    CELLS,
    close_paper_trade,
    open_paper_trade,
)


def _find(cell_id):
    return next(c for c in CELLS if c.cell_id == cell_id)


def test_bybit_perp_cells_registered():
    for cid in ("btc_bb_eq_mm_passive", "eth_bb_eq_mm_passive"):
        c = _find(cid)
        assert c.kind == "mm_passive"
        assert c.venue == "BB"
        assert c.is_perp is True
        assert c.fee_bps == 2.0


def test_per_cell_maker_fee_applied():
    perp = _find("btc_bb_eq_mm_passive")
    t = open_paper_trade(perp, fill_price=100.0)  # notional 1000, qty 10
    assert t["fee_bps"] == 2.0
    assert abs(t["fees_usd"] - 0.20) < 1e-9       # 1000 * 2/1e4
    # spot cell still uses the 25 bps taker default
    spot = open_paper_trade(_find("btc_kr_eq_mm_passive"), fill_price=100.0)
    assert spot["fee_bps"] == 25.0
    assert abs(spot["fees_usd"] - 2.50) < 1e-9


def test_mm_passive_roundtrip_captures_spread_minus_fees():
    perp = _find("btc_bb_eq_mm_passive")
    t = open_paper_trade(perp, fill_price=100.0)        # buy rests at bid 100
    close_paper_trade(t, bid=100.0, ask=100.10, mid=100.05)
    assert t["status"] == "closed"
    assert t["funding_pnl_usd"] == 0.0                  # rate 0 -> no funding
    expected = 1.00 - 0.20 - (100.10 * 10 * 2 / 1e4)    # gross - entry - exit
    assert abs(t["realized_pnl_usd"] - expected) < 1e-6
    assert t["realized_pnl_usd"] > 0    # 10 bps spread beats 4 bps round-trip


def test_perp_funding_long_pays_short_receives():
    perp = _find("btc_bb_eq_mm_passive")          # side buy -> long
    t = open_paper_trade(perp, fill_price=100.0, funding_rate_at_open=0.01)
    t["ts_utc"] = time.time() - 8 * 3600          # one full 8h funding cycle
    close_paper_trade(t, bid=100.0, ask=100.0, mid=100.0)   # flat price
    assert t["funding_pnl_usd"] < 0                # long pays when rate > 0
    assert abs(t["funding_pnl_usd"] - (-0.01 * 1000.0)) < 0.5

    t2 = open_paper_trade(perp, fill_price=100.0, funding_rate_at_open=0.01)
    t2["side"] = "sell"                            # short -> receives
    t2["ts_utc"] = time.time() - 8 * 3600
    close_paper_trade(t2, bid=100.0, ask=100.0, mid=100.0)
    assert t2["funding_pnl_usd"] > 0


def test_close_reason_recorded_for_gate_pull():
    perp = _find("btc_bb_eq_mm_passive")
    t = open_paper_trade(perp, fill_price=100.0)
    close_paper_trade(t, 100.0, 100.1, 100.05, close_reason="liq_burst")
    assert t["close_reason"] == "liq_burst"


def test_spot_cell_backward_compatible():
    t = open_paper_trade(_find("eth_kr_eq_mm_passive"), fill_price=100.0)
    assert t["is_perp"] is False
    close_paper_trade(t, 100.0, 100.1, 100.05)     # no close_reason -> default
    assert t["funding_pnl_usd"] == 0.0
    assert t["close_reason"] == "auto_hold_elapsed"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
