"""pool_book_kraken.py — the ONE live driver: BOOK -> live executor (front-of-line) -> GREEDY $5k pool.

This is the thing that was missing (S70): basket_sim runs the book through the live executor but skips
the allocator (sum-@-$5k); portfolio_sim runs the allocator but off TAPE capacity. Neither ran the
live greedy allocator on the live BOOK. This does exactly that and nothing else — it REUSES the live
pieces (basket_sim_kraken.load_book + run_cell front-of-line, platform.run_portfolio greedy). No
reimplementation, no tape, no queue: front-of-line only, per the operating contract.

Answer: ONE $5k bank, greedy by performance, over the per-coin BOOK legs -> pool $/hr + per-coin funding.
"""
from __future__ import annotations
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from basket_sim_kraken import load_book, run_cell, CELLS, CAP          # LIVE book loader + live run_cell
from odcore.platform import run_portfolio                              # LIVE greedy allocator

BUCKET = 3600   # hourly buckets on the 1s grid (basket_sim default)
POOL = CAP  # $5000 total bank


def main():
    # 1) load the books for active cells, find the common overlap window
    books = {}
    for cell in CELLS:
        if not cell["active"]:
            continue
        bk = load_book(cell["coin"])
        if bk is None:
            print(f"  [{cell['coin']}] no book — skip"); continue
        books[cell["coin"]] = bk
    if not books:
        print("no books; materialize /tmp/kbook/*_book.jsonl first"); return
    ov0 = max(bk["t0"] for bk in books.values())
    ov1 = min(bk["t0"] + bk["n"] - 1 for bk in books.values())
    ov_sec = ov1 - ov0 + 1
    hours = ov_sec / 3600.0
    coins = [c["coin"] for c in CELLS if c["active"] and c["coin"] in books]

    print("=== KRAKEN $5k SHARED-POOL, GREEDY, FRONT-OF-LINE — via LIVE run_cell + run_portfolio ===")
    print(f"   pool=${POOL:.0f} (ONE bank)   common book window {ov_sec}s = {hours:.1f}h across {len(coins)} coins")
    print(f"   fill = FRONT-OF-LINE (contract); kr_mk0 0bp maker\n")

    # 2) run each coin's FIXED stack through the live executor (front-of-line) on the clipped book
    cell_legs = {}
    edge = {}   # per-coin return-on-capacity ($/hr per $ at flat CAP) -> greedy funding priority
    for cell in CELLS:
        if not cell["active"] or cell["coin"] not in books:
            continue
        coin = cell["coin"]; bk = books[coin]
        s = ov0 - bk["t0"]; e = s + ov_sec
        clip = {k: (bk[k][s:e] if isinstance(bk[k], np.ndarray) else bk[k]) for k in bk}
        clip["hs"] = bk["hs"]
        _, r = run_cell(cell, clip, fill_model="front")     # LIVE, front-of-line
        cell_legs[coin] = r.legs
        edge[coin] = sum(float(l.net_bps) for l in r.legs) / 1e4 * CAP / hours   # $/hr at flat CAP

    # 3) greedy funding priority = best performer first (shift so all positive; never starve, magnitude ranks)
    lo = min(edge.values()); shift = (-lo + 1e-6) if lo <= 0 else 0.0
    weights = {c: edge[c] + shift for c in coins}

    # 4) THE greedy shared-$5k pool over the BOOK legs (live allocator)
    pr = run_portfolio(cell_legs, pool=POOL, weights=weights, mode="greedy",
                       n=ov_sec, bucket_cells=BUCKET)

    order = sorted(coins, key=lambda c: -edge[c])
    print(f"  {'coin':6}{'edge$/hr@5k':>12}{'legs':>6}{'funded':>8}{'fund%':>7}{'meanAlloc$':>12}{'realized$':>12}")
    for c in order:
        pc = pr.per_coin[c]
        print(f"  {c:6}{edge[c]:>+12.2f}{pc['n_legs']:>6}{pc['n_funded']:>8}{100*pc['fill_share']:>6.0f}%"
              f"{pc['mean_alloc_usd']:>12.0f}{pc['realized_pnl_usd']:>+12.2f}")

    print(f"\n  --- POOL (one ${POOL:.0f} bank, greedy, front-of-line) ---")
    print(f"  POOL $/hr            = {pr.pool_return_per_hr:+.2f}  (${pr.total_pnl_usd:+.2f} over {hours:.1f}h)")
    print(f"  pool utilization     = mean {100*pr.mean_util:.0f}%  peak {100*pr.max_util:.0f}%  idle {100*pr.idle_frac:.0f}%")
    print(f"  vs sum-@-$5k-each    = the OLD wrong framing; this is the ONE ${POOL:.0f} bank shared greedily.")
    print(f"\n  ⚠ caps=pool (each coin may take the full $5k up to book absorption is NOT yet applied — v1);")
    print(f"    recent {hours:.1f}h book = current conditions (the tuning surface).")


if __name__ == "__main__":
    main()
