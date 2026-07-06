"""basket_sim_kraken.py — the MULTI-SLEEVE KRAKEN BASKET SIMULATOR (S65, Job 1).

⭐ ARCHITECTURE RULE (Greg S65, load-bearing — "why are we using different code on sims than we will
be doing live? the sim runs should always be our LIVE CODE plus new pieces. do NOT rewrite sim code in
place of our actual code"): the DECISION PATH here IS the live/paper code — `odcore.platform.run_stream`
(which drives `odcore.swing_maker`, the one executor). This file ONLY adds pieces the live path doesn't
own yet: (1) Kraken L2 book LOADING (a venue run_cell has no loader for), (2) per-coin flip COMPOSITION
(early-arm/reverse via the live flip_detector), (3) the multi-sleeve PORTFOLIO/tier layer. It must never
reimplement the executor, fill model, sizing, or fees. New mechanics go into odcore/ (live), then are
used here — e.g. the enticing close is `swing_maker.close_improve_bps`, threaded through run_stream.

FILL: FRONT-OF-LINE by default (Greg S65 — "we should always be front of line when doing maker numbers").
run_stream defaults fill_model="front" = the S46 deployed premise ("have the best bid/offer, fill on the
first opposing trade"). Front-of-line is EARNED live by posting an enticing (price-improved) quote; the
cost of that is `close_improve_bps` (per-coin), applied on covers that would otherwise force to taker.

THE STACK per majors cell (STRATEGY_INVENTORY.md §2.A): flow-lean zigzag (W600/REV0.1/ARM0) + early-arm
(retime, ETH eps10/BTC eps5/SOL none) + reverse (SOL) + deep-bail (exit_spec price_stop, ETH-100/BTC-80)
+ cover-grace (300; DOGE 600) + enticing close. kr_mk0 = 0bp maker.

DATA REALITY: the only Kraken data on-box is the ~30-42h L2 BOOK (a LOW-EDGE single window). $/hr is
PROVISIONAL — the deliverable is the FILL-honest portfolio STRUCTURE, re-runnable on a normal-edge Tardis
window. Sleeves not on this data: eligible-basket (-2bp, tape-only), E300 (Coinbase) — flagged off.

Usage:
  python scripts/basket_sim_kraken.py                 # front-of-line, per-coin enticing
  python scripts/basket_sim_kraken.py --improve 0     # disable enticing (measure its contribution)
  python scripts/basket_sim_kraken.py --fill queue    # back-of-line reference (pessimistic bound)
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.flip_detector import lean_series, detect_flips, retime_flips  # noqa: E402  (flip composition)
from odcore.platform import run_stream                                    # noqa: E402  (THE LIVE DECISION PATH)

CAP = 5000.0
WFLIP, REV = 600, 0.1
KBOOK = "/tmp/kbook"
MAKER_FEE = 0.0        # kr_mk0
TAKER_FEE = 5.0        # taker fallback / deep-bail cross (representative Kraken)

# ---- per-coin deployed config (STRATEGY_INVENTORY.md §2.A) + enticing (S65) ----
# improve = per-coin close_improve_bps (enticing concession). Set from the enticing sweep: use it where
# it lifts, 0 where it hurts. active=True runs book-honest here.
# ⚠ S65 DIRECTION RE-ADJUDICATION employed (agent finding, `_kraken_readjudicate.py`): on the BOOK window
# FORWARD wins all 5 coins. eth/btc keep deployed fwd+early-arm (early-arm HELPS eth on book, +6.77 vs base
# +3.42; per-coin). SOL flipped to FWD here (book: FWD +6.51 > REV +2.17) — but the 30d-TAPE deploy map says
# REVERSED; this is a book-window re-adjudication, NOT an overturn — needs a 30d-tape/Tardis confirm. DOGE
# activated FWD flow-lean (book +5.46) though deployed signal is fade-8h. XRP FWD (was stand-aside).
CELLS = [
    dict(coin="eth", sleeve="majors", side=+1, eps=10.0, bail=100.0, grace=300, improve=0.5, active=True),
    dict(coin="btc", sleeve="majors", side=+1, eps=5.0,  bail=80.0,  grace=300, improve=0.5, active=True),
    dict(coin="sol", sleeve="majors", side=+1, eps=None, bail=None,  grace=300, improve=0.5, active=True,
         note="RE-ADJUDICATED FWD on book (FWD +6.51 > REV +2.17); tape deploy=reversed — needs tape confirm"),
    dict(coin="doge", sleeve="majors", side=+1, eps=None, bail=None, grace=600, improve=0.5, active=True,
         note="RE-ADJUDICATED: base flow-lean FWD +5.46 on book; deployed signal=fade-8h — provisional"),
    dict(coin="xrp", sleeve="majors", side=+1, eps=None, bail=None, grace=300, improve=0.5, active=True,
         note="RE-ADJUDICATED FWD +14.02 (was stand-aside, S63 z=0.7 on tape)"),
]


def load_book(coin):
    """L2 book jsonl -> (t0_sec, arrays on a uniform 1-sec grid). Kraken venue DATA I/O — the one thing
    the live run_cell has no loader for; the decision itself goes through run_stream (live)."""
    path = f"{KBOOK}/{coin}_book.jsonl"
    if not os.path.exists(path):
        return None
    ts_l, mid_l, bb_l, ba_l, buy_l, sell_l, sp_l = [], [], [], [], [], [], []
    with open(path) as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            ts_l.append(d["ts"]); mid_l.append(d["mid"]); sp_l.append(d.get("spread", 0.0))
            bb_l.append(d["bids"][0][1] if d.get("bids") else 0.0)
            ba_l.append(d["asks"][0][1] if d.get("asks") else 0.0)
            buy_l.append(d.get("buy", 0.0)); sell_l.append(d.get("sell", 0.0))
    sec = np.array(ts_l).astype(np.int64)
    t0, t1 = int(sec.min()), int(sec.max()); n = t1 - t0 + 1
    mid = np.zeros(n); bb = np.zeros(n); ba = np.zeros(n); buy = np.zeros(n); sell = np.zeros(n)
    sp = np.zeros(n); have = np.zeros(n, bool)
    idx = (sec - t0).astype(int)
    mid_a, bb_a, ba_a = np.array(mid_l), np.array(bb_l), np.array(ba_l)
    buy_a, sell_a, sp_a = np.array(buy_l), np.array(sell_l), np.array(sp_l)
    for i in range(len(idx)):
        j = idx[i]
        mid[j] = mid_a[i]; bb[j] = bb_a[i]; ba[j] = ba_a[i]; sp[j] = sp_a[i]
        buy[j] += buy_a[i]; sell[j] += sell_a[i]; have[j] = True
    fi = np.where(have, np.arange(n), 0); np.maximum.accumulate(fi, out=fi)
    first = int(np.argmax(have))
    for arr in (mid, bb, ba, sp):
        arr[:] = arr[fi]; arr[:first] = arr[first]
    hs_bps = float(np.median((sp[mid > 0] / mid[mid > 0]) / 2.0) * 1e4)
    return dict(t0=t0, mid=mid, bb=bb, ba=ba, buy=buy, sell=sell, hs=hs_bps, n=n)


def flips_for(cell, mid, buy, sell):
    """Per-coin flip COMPOSITION via the live flip_detector: early-arm (retime) if eps set else base
    detect_flips; reverse for reversed cells (SOL). (Signal composition, not executor logic.)"""
    if cell["eps"] is not None:
        entries, _ = retime_flips(mid, buy, sell, WFLIP, REV, cell["eps"])
    else:
        entries, _ = detect_flips(lean_series(buy, sell, WFLIP), REV)
    if cell["side"] < 0:
        entries = [(ci, pv, -s) for (ci, pv, s) in entries]
    return entries


def run_cell(cell, bk, fill_model="front", improve=None):
    """Full-stack cell run THROUGH THE LIVE DECISION PATH (platform.run_stream). Deep-bail = exit_spec
    price_stop; cover_grace + enticing (close_improve_bps) recover the maker fill; kr_mk0 fees."""
    mid, bb, ba, buy, sell, hs = bk["mid"], bk["bb"], bk["ba"], bk["buy"], bk["sell"], bk["hs"]
    entries = flips_for(cell, mid, buy, sell)
    exit_spec = {"kind": "price_stop", "x_bp": float(cell["bail"]), "action": "flat", "side": 0} \
        if cell["bail"] is not None else None
    imp = cell["improve"] if improve is None else improve
    res, _ = run_stream(mid, buy, sell, entries, best_bid_sz=bb, best_ask_sz=ba,
                        half_spread_bps=hs, maker_fee=MAKER_FEE, taker_fee=TAKER_FEE,
                        grace=cell["grace"], exit_spec=exit_spec, fill_model=fill_model,
                        queue_frac=1.0, close_improve_bps=imp)
    return entries, res


def bucket_pnl(legs, m, bucket_sec):
    nb = max(1, m // bucket_sec)
    pnl = np.zeros(nb); active = np.zeros(nb, bool)
    for l in legs:
        b = min(int(l.close_idx) // bucket_sec, nb - 1)
        pnl[b] += float(l.net_bps) / 1e4 * CAP
        o = int(l.open_idx) // bucket_sec; c = int(l.close_idx) // bucket_sec
        active[max(0, o):min(nb, c + 1)] = True
    return pnl, float(active.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", type=int, default=3600)
    ap.add_argument("--fill", default="front", choices=["front", "queue"], help="front-of-line (deployed) or queue (back-of-line ref)")
    ap.add_argument("--improve", type=float, default=None, help="override per-coin enticing concession bps")
    args = ap.parse_args()
    B = args.bucket

    print("=== KRAKEN MULTI-SLEEVE BASKET SIMULATOR (S65 Job 1) — via LIVE run_stream, front-of-line ===")
    print(f"   kr_mk0 (maker={MAKER_FEE}bp, taker={TAKER_FEE}bp); fill={args.fill}; $/hr @ ${CAP:.0f}/cell; bucket={B}s\n")

    books = {}
    for cell in CELLS:
        if not cell["active"]:
            continue
        bk = load_book(cell["coin"])
        if bk is None:
            print(f"  [{cell['coin']}] no book — skip"); cell["active"] = False; continue
        books[cell["coin"]] = bk
    if not books:
        print("  no books; materialize /tmp/kbook/*_book.jsonl first"); return
    ov0 = max(bk["t0"] for bk in books.values())
    ov1 = min(bk["t0"] + bk["n"] - 1 for bk in books.values())
    ov_sec = ov1 - ov0 + 1; ov_hrs = ov_sec / 3600.0
    print(f"  COMMON overlap window: {ov_sec}s = {ov_hrs:.1f}h across {len(books)} cells\n")

    print(f"  {'cell':6}{'flips':>7} | {'$/hr':>8}{'fill%':>7}{'tkCl%':>7}{'win%':>6}{'legs':>6}"
          f"{'idle%':>7}{'entice+':>9}   stack")
    streams = {}; dphs = {}
    for cell in CELLS:
        if not cell["active"]:
            continue
        coin = cell["coin"]; bk = books[coin]
        s = ov0 - bk["t0"]; e = s + ov_sec
        clip = {k: (bk[k][s:e] if isinstance(bk[k], np.ndarray) else bk[k]) for k in bk}
        clip["hs"] = bk["hs"]
        _, r = run_cell(cell, clip, args.fill, args.improve)          # per-coin enticing (or override)
        _, r0 = run_cell(cell, clip, args.fill, 0.0)                  # same cell, enticing OFF
        dph = r.total_net_bps / 1e4 * CAP / ov_hrs
        dph0 = r0.total_net_bps / 1e4 * CAP / ov_hrs
        tk = 100 * r.n_taker_closes / r.n_legs if r.n_legs else 0.0
        pnl, active = bucket_pnl(r.legs, ov_sec, B)
        streams[coin] = pnl; dphs[coin] = dph
        rev = "*" if cell["side"] < 0 else " "
        arm = f"a{int(cell['eps'])}" if cell["eps"] else "--"
        bail = f"b{int(cell['bail'])}" if cell["bail"] else "--"
        imp = args.improve if args.improve is not None else cell["improve"]
        print(f"  {coin+rev:6}{r.n_flips:>7} | {dph:>+8.2f}{100*r.fill_rate:>6.0f}%{tk:>6.0f}%"
              f"{100*r.win_frac:>5.0f}%{r.n_legs:>6}{100*(1-active):>6.0f}%{dph-dph0:>+9.2f}   [{arm} {bail} e{imp}]")

    coins = [c for c in streams if streams[c].std() > 0]
    print(f"\n  --- PORTFOLIO ({args.fill}, {B}s buckets, equal ${CAP:.0f}/cell) ---")
    if len(coins) >= 2:
        M = np.vstack([streams[c] for c in coins]); corr = np.corrcoef(M)
        print("  correlation:   " + "".join(f"{c:>7}" for c in coins))
        for i, c in enumerate(coins):
            print(f"    {c:>6}    " + "".join(f"{corr[i, j]:>7.2f}" for j in range(len(coins))))
        sh = lambda x: float(x.mean() / (x.std() + 1e-12))
        cell_sh = {c: sh(streams[c]) for c in coins}
        port = M.sum(axis=0); port_sh = sh(port)
        mean_sh = float(np.mean(list(cell_sh.values())))
        print(f"  per-cell Sharpe/bucket: " + "  ".join(f"{c}={cell_sh[c]:+.3f}" for c in coins))
        print(f"  portfolio Sharpe/bucket = {port_sh:+.3f}  (best single {max(cell_sh.values()):+.3f}; "
              f"uncorrelated-ideal ~{mean_sh*np.sqrt(len(coins)):+.3f})")
        print(f"  aggregate $/hr (sum @ ${CAP:.0f} each) = {sum(dphs[c] for c in coins):+.2f}  "
              f"(total capital ${CAP*len(coins):.0f})")

    print("\n  --- not graded on this data ---")
    for cell in CELLS:
        if not cell["active"]:
            print(f"    [{cell['coin']:5}] {cell.get('reason','inactive')}")
    print("    [eligible-basket] APE/RE/XDC/SHX/AIOZ/ARPA @ -2bp — no Kraken book here (tape-only)")
    print("    [E300 sleeve]     family B (Coinbase) — separate data")
    print(f"\n  entice+ = $/hr the enticing close adds vs improve=0 (same cell). ⚠ one ~30h LOW-EDGE window.")


if __name__ == "__main__":
    main()
