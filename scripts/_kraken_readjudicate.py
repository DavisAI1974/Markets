"""_kraken_readjudicate.py — EMPLOY the agents' finding: re-adjudicate DIRECTION per coin (S65).

Execution agent (one 30h book window): FORWARD is the correct sign for all 5 coins on the BOOK,
contradicting deployed SOL=reversed and XRP=aside (both 30d-TAPE calls). Dipole agent: XRP wants the
plain un-gated ride. This measures forward vs reversed per coin at FRONT-OF-LINE (base flow-lean, no
early-arm — the agent found early-arm window-fragile) so we can EMPLOY the winning sign per coin.

⚠ ONE 30h book window — this RE-ADJUDICATES (measures) the sign; it does not overturn the 30d-tape
deploy map until a 30d-tape / Tardis confirm. Flagged provisional.

Usage:  python scripts/_kraken_readjudicate.py
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.flip_detector import lean_series, detect_flips             # noqa: E402
from odcore.platform import run_stream                                 # noqa: E402  (live path)
from basket_sim_kraken import CAP, load_book, MAKER_FEE, TAKER_FEE, WFLIP, REV  # noqa: E402

COINS = ["eth", "btc", "sol", "xrp", "doge"]
DEPLOYED_SIDE = {"eth": +1, "btc": +1, "sol": -1, "doge": +1, "xrp": 0}   # 0 = stand-aside


def run(bk, side):
    mid, bb, ba, buy, sell, hs = bk["mid"], bk["bb"], bk["ba"], bk["buy"], bk["sell"], bk["hs"]
    flips, _ = detect_flips(lean_series(buy, sell, WFLIP), REV)
    if side < 0:
        flips = [(c, p, -s) for (c, p, s) in flips]
    res, _ = run_stream(mid, buy, sell, flips, best_bid_sz=bb, best_ask_sz=ba,
                        half_spread_bps=hs, maker_fee=MAKER_FEE, taker_fee=TAKER_FEE,
                        grace=300, fill_model="front", close_improve_bps=0.5)
    return res


def main():
    print("=== KRAKEN DIRECTION RE-ADJUDICATION (front-of-line, base flow-lean) — employ the agent finding ===")
    print(f"   {'coin':6}{'fwd $/hr':>10}{'rev $/hr':>10}{'winner':>9}{'deployed':>10}{'flag':>22}")
    for coin in COINS:
        bk = load_book(coin)
        if bk is None:
            print(f"   {coin:6}  (no book)"); continue
        hrs = bk["n"] / 3600.0
        rf = run(bk, +1); rr = run(bk, -1)
        fwd = rf.total_net_bps / 1e4 * CAP / hrs
        rev = rr.total_net_bps / 1e4 * CAP / hrs
        winner = "FWD" if fwd > rev else "REV"
        dep = {1: "fwd", -1: "rev", 0: "aside"}[DEPLOYED_SIDE[coin]]
        flag = ""
        if (winner == "FWD" and DEPLOYED_SIDE[coin] < 0) or (winner == "REV" and DEPLOYED_SIDE[coin] > 0):
            flag = "CONTRADICTS deploy"
        elif DEPLOYED_SIDE[coin] == 0:
            flag = "was stand-aside"
        print(f"   {coin:6}{fwd:>+10.2f}{rev:>+10.2f}{winner:>9}{dep:>10}{flag:>22}")
    print("\n  front-of-line, close_improve 0.5, base flow-lean (no early-arm). ⚠ ONE 30h window — re-adjudicate,")
    print("  do NOT overturn the 30d-tape deploy map until a 30d-tape/Tardis confirm. FWD>REV on the book != deploy.")


if __name__ == "__main__":
    main()
