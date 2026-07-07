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

    # 2) run each coin's FIXED stack through the live executor (front-of-line) on the clipped book.
    #    Keep the clipped book (incl. the S71 resting-depth arrays) so we can size per-leg capacity.
    cell_legs = {}
    clips = {}
    edge = {}   # per-coin return-on-capacity ($/hr per $ at flat CAP) -> greedy funding priority
    for cell in CELLS:
        if not cell["active"] or cell["coin"] not in books:
            continue
        coin = cell["coin"]; bk = books[coin]
        s = ov0 - bk["t0"]; e = s + ov_sec
        clip = {k: (bk[k][s:e] if isinstance(bk[k], np.ndarray) else bk[k]) for k in bk}
        # bid_depth/ask_depth are dicts {N: array} — clip each depth array to the overlap window too
        clip["bid_depth"] = {N: bk["bid_depth"][N][s:e] for N in bk["bid_depth"]}
        clip["ask_depth"] = {N: bk["ask_depth"][N][s:e] for N in bk["ask_depth"]}
        clip["hs"] = bk["hs"]
        clips[coin] = clip
        _, r = run_cell(cell, clip, fill_model="front")     # LIVE, front-of-line
        cell_legs[coin] = r.legs
        edge[coin] = sum(float(l.net_bps) for l in r.legs) / 1e4 * CAP / hours   # $/hr at flat CAP

    # 3) greedy funding priority = best performer first (shift so all positive; never starve, magnitude ranks)
    lo = min(edge.values()); shift = (-lo + 1e-6) if lo <= 0 else 0.0
    weights = {c: edge[c] + shift for c in coins}

    def build_leg_caps(nlev):
        """Per-leg counterparty capacity = summed RESTING depth ($) over the top-`nlev` book levels on
        the COUNTER side at the leg's open (Greg S71: resting bid/ask depth, NOT traded buy/sell volume).
        A LONG leg (side +1) is filled by sellers -> counter = ask depth; a SHORT leg -> bid depth."""
        lc = {}
        for c in coins:
            ad = clips[c]["ask_depth"][nlev]; bd = clips[c]["bid_depth"][nlev]
            caps_c = []
            for l in cell_legs[c]:
                o = int(l.open_idx)
                counter = ad if int(l.side) > 0 else bd
                caps_c.append(float(counter[min(o, len(counter) - 1)]))
            lc[c] = caps_c
        return lc

    def run_and_report(leg_caps, label):
        pr = run_portfolio(cell_legs, pool=POOL, weights=weights, mode="greedy",
                           n=ov_sec, bucket_cells=BUCKET, leg_caps=leg_caps)
        avail = sum(len(cell_legs[c]) for c in coins)
        funded = sum(pr.per_coin[c]["n_funded"] for c in coins)
        print(f"\n  === {label} ===")
        print(f"  {'coin':6}{'edge$/hr@5k':>12}{'legs':>6}{'funded':>8}{'fund%':>7}{'meanAlloc$':>12}{'realized$':>12}")
        for c in sorted(coins, key=lambda c: -edge[c]):
            pc = pr.per_coin[c]
            print(f"  {c:6}{edge[c]:>+12.2f}{pc['n_legs']:>6}{pc['n_funded']:>8}{100*pc['fill_share']:>6.0f}%"
                  f"{pc['mean_alloc_usd']:>12.0f}{pc['realized_pnl_usd']:>+12.2f}")
        print(f"  POOL $/hr = {pr.pool_return_per_hr:+.2f}  (${pr.total_pnl_usd:+.2f}/{hours:.1f}h)   "
              f"funded {funded}/{avail} ({100*funded/avail:.0f}%)   time-in-play {100*pr.time_in_play_frac:.0f}%   "
              f"time-deploy {100*pr.time_util:.0f}%")
        return pr, funded, avail

    # 4a) BASELINE — per-coin cap = pool (caps=None): the best coin monopolizes the $5k (serializes).
    pr0, funded0, avail0 = run_and_report(None, "BASELINE  (caps=pool: one coin at a time)")

    # 4b) THE LEVER — per-leg counterparty capacity from RESTING BOOK DEPTH, swept over depth levels.
    #     Shallow (touch/L1) = what a front-of-line maker fills first (binds < $5k -> forces concurrency);
    #     full 10-level = the whole resting book (deep -> rarely binds a $5k position).
    print(f"\n  --- PER-LEG CAPACITY = RESTING BOOK DEPTH (counter side), swept by # levels summed ---")
    best = (pr0.pool_return_per_hr, None, "baseline")
    for nlev in (1, 2, 3, 5, 10):
        lc = build_leg_caps(nlev)
        pr, funded, avail = run_and_report(lc, f"leg-cap = resting depth, top-{nlev} level(s)")
        if pr.pool_return_per_hr > best[0]:
            best = (pr.pool_return_per_hr, nlev, f"top-{nlev}")

    # ---- concurrency of WANT (context: how many coins want in at once) ----
    nsec = ov_sec
    live = {c: np.zeros(nsec, bool) for c in coins}
    for c in coins:
        for l in cell_legs[c]:
            live[c][int(l.open_idx):int(l.close_idx) + 1] = True
    conc = np.sum(np.vstack([live[c] for c in coins]), axis=0)
    mean_conc_when_active = float(conc[conc > 0].mean()) if np.any(conc > 0) else 0.0
    print(f"\n  --- context ---")
    print(f"  a coin wants in {100*float((conc>0).mean()):.0f}% of the time; when active, "
          f"{mean_conc_when_active:.2f} coins want in at once (the concurrency headroom).")
    print(f"  BEST config: {best[2]}  ->  POOL {best[0]:+.2f} $/hr   (baseline serialized = {pr0.pool_return_per_hr:+.2f})")
    print(f"  (recent {hours:.1f}h book = current conditions, low per-leg edge; firing untouched — FILL/capacity layer.)")


if __name__ == "__main__":
    main()
