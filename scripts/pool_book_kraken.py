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
    print(f"  MONEY IN PLAY        = {100*pr.time_in_play_frac:.0f}% of the {hours:.1f}h (wall-clock; ANY capital deployed)")
    print(f"  TIME-weighted deploy = {100*pr.time_util:.0f}% of the $5k on average "
          f"(vs the misleading event-sampled {100*pr.mean_util:.0f}%)")

    # ---- CAPACITY OVER TIME (the real question — not the $5k snapshot) ----
    # TIME-weighted, uniform over the whole window (NOT event-sampled like mean_util).
    nsec = ov_sec
    live = {c: np.zeros(nsec, bool) for c in coins}       # when each coin WANTS to be live (raw legs)
    for c in coins:
        for l in cell_legs[c]:
            live[c][int(l.open_idx):int(l.close_idx) + 1] = True
    conc = np.sum(np.vstack([live[c] for c in coins]), axis=0)   # # coins wanting to be live each sec
    any_live = float((conc > 0).mean())
    mean_conc_when_active = float(conc[conc > 0].mean()) if np.any(conc > 0) else 0.0

    # deployed $ over time UNDER caps=pool greedy: one coin holds the full $5k, so deployed = $5k
    # whenever the funded coin holds. Reconstruct held-$ timeline from the funded legs.
    avail = sum(len(cell_legs[c]) for c in coins)
    funded = sum(pr.per_coin[c]["n_funded"] for c in coins)
    print(f"\n  --- CAPACITY OVER TIME (time-weighted, {hours:.1f}h) ---")
    print(f"  opportunity: a coin WANTS to trade {100*any_live:.0f}% of the time; when active, "
          f"{mean_conc_when_active:.2f} coins want in at once")
    print(f"  legs AVAILABLE across coins = {avail}   |   legs FUNDED by the $5k = {funded}   "
          f"({100*funded/avail:.0f}%)  ->  {avail-funded} legs DROPPED ({100*(avail-funded)/avail:.0f}%)")
    print(f"  concurrency of WANT (frac of time N coins want in simultaneously):")
    for k in range(len(coins) + 1):
        f = float((conc == k).mean())
        if f > 0.005:
            print(f"     {k} coins: {100*f:4.0f}%")
    print(f"\n  ⇒ caps=pool SERIALIZES: one coin takes the whole $5k and BLOCKS the others until it closes,"
          f"\n    so we fund ~1 coin at a time and DROP the {100*(avail-funded)/avail:.0f}% of legs that overlap a held position.")
    print(f"    THE lost volume = per-coin caps < $5k would let {mean_conc_when_active:.1f} coins run at once on the same $5k.")
    print(f"    (recent {hours:.1f}h book = current conditions; firing untouched — this is the FILL/capacity layer.)")


if __name__ == "__main__":
    main()
