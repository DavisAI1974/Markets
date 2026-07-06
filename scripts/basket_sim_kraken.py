"""basket_sim_kraken.py — the MULTI-SLEEVE KRAKEN BASKET SIMULATOR (S65, Job 1).

Puts an honest $/hr + Sharpe on the two-sleeve+basket Kraken architecture, running the FULL per-coin
deployed stack (NOT bare lean — Greg's S64 warning) through the REAL executor `odcore.swing_maker`.

THE STACK per majors cell (STRATEGY_INVENTORY.md §2.A, reconciled S65):
  core        flow-lean zigzag  flip_detector.lean_series(W=600) + detect_flips(REV=0.1), ARM0
  + early-arm retime_flips(eps)     ETH eps10 / BTC eps5 / SOL none (hurts SOL)
  + reverse   SOL only (anti-predictive on Kraken spot)
  + deep-bail exit_spec price_stop  ETH -100 / BTC -80 / SOL none  (taker flatten at big depth)
  + cover-grace  swing_maker cover_grace  300 (DOGE 600) — recover the maker fill past the turn
  fees        kr_mk0 = 0bp maker; taker fallback ~5bp; deep-bail cross ~taker
  [E300-on-BTC death-cut: marginal +0.20, window-fragile — HOOKED (--e300) but classifier not wired v1]

SLEEVES (the architecture — S64):
  majors    ETH/BTC/SOL book-honest here; unlocks the $10M/30d 0bp tier via deep volume.
  eligible  APE/RE/XDC/SHX/AIOZ/ARPA @ -2bp rebate — NO Kraken book on this data -> tape-only, FLAGGED off.
  E300      family B, Coinbase data -> separate; correlation is a later job. FLAGGED off.

DATA REALITY (flag in every read): the only Kraken data on-box is the ~30-42h L2 BOOK
(data/*-kraken-book) — a LOW-EDGE single window (S64: ETH ideal-fill already ~-2 on it). So the
$/hr here is NOT the +8-9/hr 30d-tape regime; what this delivers is the STRUCTURE + the real
FILL-honest portfolio Sharpe/correlation framework, re-runnable on a normal-edge Tardis window.

Portfolio: per-cell PnL bucketed on the COMMON overlap window -> correlation matrix + equal-weight
portfolio Sharpe vs best single cell (the diversification / sqrt(N) story) + per-cell idle%.

Usage:
  python scripts/basket_sim_kraken.py                 # majors sleeve, honest+ideal fill
  python scripts/basket_sim_kraken.py --bucket 1800   # 30-min PnL buckets for the Sharpe
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from odcore.flip_detector import lean_series, detect_flips, retime_flips  # noqa: E402
from odcore.swing_maker import simulate_swing_maker                       # noqa: E402

CAP = 5000.0
WFLIP, REV = 600, 0.1
KBOOK = "/tmp/kbook"
MAKER_FEE = 0.0        # kr_mk0
TAKER_FEE = 5.0        # taker fallback / deep-bail cross (representative Kraken)

# ---- per-coin deployed config (STRATEGY_INVENTORY.md §2.A FINAL PER-COIN CONFIG) ----
# active=True cells run book-honest here; inactive carry the reason they can't on this data.
CELLS = [
    dict(coin="eth", sleeve="majors", side=+1, eps=10.0, bail=100.0, grace=300, e300=False, active=True),
    dict(coin="btc", sleeve="majors", side=+1, eps=5.0,  bail=80.0,  grace=300, e300=True,  active=True),
    dict(coin="sol", sleeve="majors", side=-1, eps=None, bail=None,  grace=300, e300=False, active=True),
    dict(coin="doge", sleeve="majors", side=+1, eps=None, bail=None, grace=600, e300=False, active=False,
         reason="deployed signal = fade-8h (tape-graded, 8h warmup) — too thin on a 30h book; tape-only"),
    # XRP: deployed status = stand-aside (S63 z=0.7, nothing clears) — but Greg (S65) wants it IN.
    # Run the base flow-lean forward as an EXPLORATORY cell; the piece-audit agents hunt its real config.
    dict(coin="xrp", sleeve="majors", side=+1, eps=None, bail=None, grace=300, e300=False, active=True,
         note="EXPLORATORY — no deployed solution; base flow-lean forward, no early-arm/bail"),
    # eligible-basket + E300 sleeves: no Kraken book on this data -> off, tape/Coinbase only.
]


def load_book(coin):
    """L2 book jsonl -> (t0_sec, arrays on a uniform 1-sec grid). Same recipe as
    _s63_kraken_makerfill.load_book_1s but returns the absolute t0 so cells share one grid."""
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
    """Compose the cell's entry signal: early-arm (retime) if eps set, else base detect_flips;
    reverse the side for reversed cells (SOL)."""
    if cell["eps"] is not None:
        entries, _ = retime_flips(mid, buy, sell, WFLIP, REV, cell["eps"])
    else:
        lean = lean_series(buy, sell, WFLIP)
        entries, _ = detect_flips(lean, REV)
    if cell["side"] < 0:
        entries = [(ci, pv, -s) for (ci, pv, s) in entries]
    return entries


def run_cell(cell, bk, fill_model):
    """Full-stack run of one cell through the real executor. deep-bail = exit_spec price_stop (taker
    flatten at fav <= -bail); cover_grace recovers maker fills; kr_mk0 fees."""
    mid, bb, ba, buy, sell, hs = bk["mid"], bk["bb"], bk["ba"], bk["buy"], bk["sell"], bk["hs"]
    entries = flips_for(cell, mid, buy, sell)
    exit_spec = None
    if cell["bail"] is not None:
        exit_spec = {"kind": "price_stop", "x_bp": float(cell["bail"]), "action": "flat", "side": 0}
    r = simulate_swing_maker(mid, bb, ba, buy, sell, entries,
                             half_spread_bps=hs, maker_fee_bps=MAKER_FEE, taker_fee_bps=TAKER_FEE,
                             cover_grace=cell["grace"], exit_spec=exit_spec,
                             fill_model=fill_model, queue_frac=1.0)
    return entries, r


def bucket_pnl(legs, m, bucket_sec):
    """Per-cell $ PnL bucketed by close time over [0, m) seconds -> aligned vector for correlation.
    Also returns fraction of buckets with an open position (approx idle = 1 - active)."""
    nb = max(1, m // bucket_sec)
    pnl = np.zeros(nb)
    active = np.zeros(nb, bool)
    for l in legs:
        b = min(int(l.close_idx) // bucket_sec, nb - 1)
        pnl[b] += float(l.net_bps) / 1e4 * CAP
        o = int(l.open_idx) // bucket_sec; c = int(l.close_idx) // bucket_sec
        active[max(0, o):min(nb, c + 1)] = True
    return pnl, float(active.mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bucket", type=int, default=3600, help="PnL bucket seconds for Sharpe/corr")
    args = ap.parse_args()
    B = args.bucket

    print("=== KRAKEN MULTI-SLEEVE BASKET SIMULATOR (S65 Job 1) — full per-coin stack, real executor ===")
    print(f"   kr_mk0 (maker={MAKER_FEE}bp, taker={TAKER_FEE}bp); $/hr @ ${CAP:.0f}/cell; bucket={B}s\n")

    # load active cells + compute the COMMON overlap window (for the portfolio correlation/Sharpe)
    books = {}
    for cell in CELLS:
        if not cell["active"]:
            continue
        bk = load_book(cell["coin"])
        if bk is None:
            print(f"  [{cell['coin']}] no book at {KBOOK} — skip"); cell["active"] = False; continue
        books[cell["coin"]] = bk
    if not books:
        print("  no books materialized. Run: git show origin/data/<coin>-kraken-book:"
              "<coin>_kraken_book.jsonl.gz | gunzip > /tmp/kbook/<coin>_book.jsonl"); return
    ov0 = max(bk["t0"] for bk in books.values())
    ov1 = min(bk["t0"] + bk["n"] - 1 for bk in books.values())
    ov_sec = ov1 - ov0 + 1
    ov_hrs = ov_sec / 3600.0
    print(f"  COMMON overlap window: {ov_sec}s = {ov_hrs:.1f}h across {len(books)} book-graded cells\n")

    # per-cell run on the clipped common window (ideal + honest fill), collect PnL streams
    print(f"  {'cell':6}{'hs_bp':>7}{'flips':>7} | {'IDEAL$/h':>9}{'fill%':>7} || "
          f"{'HONEST$/h':>10}{'fill%':>7}{'tkCl%':>7}{'win%':>6}{'legs':>6}{'idle%':>7}")
    streams = {}
    honest_dph = {}
    for cell in CELLS:
        if not cell["active"]:
            continue
        coin = cell["coin"]; bk = books[coin]
        s = ov0 - bk["t0"]; e = s + ov_sec
        clip = {k: (bk[k][s:e] if isinstance(bk[k], np.ndarray) else bk[k]) for k in bk}
        clip["hs"] = bk["hs"]
        ent_i, ideal = run_cell(cell, clip, "front")
        ent_h, honest = run_cell(cell, clip, "queue")
        idph = ideal.total_net_bps / 1e4 * CAP / ov_hrs
        hdph = honest.total_net_bps / 1e4 * CAP / ov_hrs
        tk = 100 * honest.n_taker_closes / honest.n_legs if honest.n_legs else 0.0
        pnl, active = bucket_pnl(honest.legs, ov_sec, B)
        streams[coin] = pnl; honest_dph[coin] = hdph
        rev = "*" if cell["side"] < 0 else " "
        arm = f"a{int(cell['eps'])}" if cell["eps"] else "--"
        bail = f"b{int(cell['bail'])}" if cell["bail"] else "--"
        tag = f"{coin}{rev}"
        print(f"  {tag:6}{bk['hs']:>7.2f}{ideal.n_flips:>7} | {idph:>+9.2f}{100*ideal.fill_rate:>6.0f}% || "
              f"{hdph:>+10.2f}{100*honest.fill_rate:>6.0f}%{tk:>6.0f}%{100*honest.win_frac:>5.0f}%"
              f"{honest.n_legs:>6}{100*(1-active):>6.0f}%   [{arm} {bail}]")

    # ---- portfolio: correlation + equal-weight Sharpe vs best single cell (the diversification story) ----
    coins = [c for c in streams if streams[c].std() > 0]
    print(f"\n  --- PORTFOLIO (honest fill, {B}s buckets, equal ${CAP:.0f}/cell) ---")
    if len(coins) < 2:
        print("  <2 cells with variance — no portfolio stat.");
    else:
        M = np.vstack([streams[c] for c in coins])
        corr = np.corrcoef(M)
        print("  correlation (honest per-bucket PnL):")
        print("        " + "".join(f"{c:>7}" for c in coins))
        for i, c in enumerate(coins):
            print(f"    {c:>4}" + "".join(f"{corr[i, j]:>7.2f}" for j in range(len(coins))))
        # per-cell Sharpe (per-bucket), portfolio equal-weight Sharpe
        def sharpe(x):
            return float(x.mean() / (x.std() + 1e-12))
        cell_sh = {c: sharpe(streams[c]) for c in coins}
        port = M.sum(axis=0)
        port_sh = sharpe(port)
        best = max(cell_sh.values())
        mean_sh = float(np.mean(list(cell_sh.values())))
        # sqrt(N) ideal: if cells were uncorrelated & equal-Sharpe, portfolio Sharpe = single * sqrt(N)
        sqrtN = mean_sh * np.sqrt(len(coins))
        print(f"\n  per-cell Sharpe/bucket: " + "  ".join(f"{c}={cell_sh[c]:+.3f}" for c in coins))
        print(f"  portfolio Sharpe/bucket = {port_sh:+.3f}   (best single {best:+.3f}; "
              f"mean single {mean_sh:+.3f}; uncorrelated-ideal ~{sqrtN:+.3f})")
        agg = sum(honest_dph[c] for c in coins)
        print(f"  aggregate honest $/hr (sum of cells @ ${CAP:.0f} each) = {agg:+.2f}  "
              f"(total capital ${CAP*len(coins):.0f})")

    # ---- inactive cells + sleeves not on this data ----
    print("\n  --- NOT graded on this data (flagged) ---")
    for cell in CELLS:
        if not cell["active"]:
            print(f"    [{cell['coin']:5}] {cell.get('reason','inactive')}")
    print("    [eligible-basket] APE/RE/XDC/SHX/AIOZ/ARPA @ -2bp — no Kraken book on this data (tape-only)")
    print("    [E300 sleeve]     family B (Coinbase) — separate data; correlation is a later job")

    print("\n  ⚠ CAVEATS (do NOT over-read): ~30h LOW-EDGE single book window (S64: ETH ideal-fill ~-2 here),")
    print("    NOT the +8-9/hr 30d-tape regime. Numbers are PROVISIONAL — the deliverable is the FILL-honest")
    print("    portfolio STRUCTURE, re-runnable on a normal-edge Tardis window. E300-on-BTC not wired v1.")


if __name__ == "__main__":
    main()
