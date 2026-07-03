"""_s54_backfill_sweep.py — run the S54 measurements on the DEEP history (Bybit trade-dump
backfill bins, 30d x 5 coins) instead of the one 29-196h book window per cell.

Two questions, both n-starved on the books, settled here:
  1. THE BELL (Greg): does the coarse dipole flip mark real direction changes at his cadence?
     The pooled book sweep showed a gradient (P(real) 0.50 -> 0.59 toward coarser scale) that
     was a 1.7-sigma whisper on n=93. 30 days x 5 coins gives thousands of coarse turns.
  2. THE BIG LINE multi-window gate: does the adaptive aligned engine (f0.25/w4h, the 4/5-coin
     +$1-4/hr result) reproduce across 30 days / per-week splits on an independent venue's tape?

Cells here are bybit_perp (trade-derived 1-sec bins: mid = last trade, buy/sell = taker flow).
Per-cell discipline: these are DIFFERENT cells from the Coinbase books — this validates the
MECHANISM at scale; deploy numbers stay per-venue. Fees: Bybit standard taker 5.5bp is used for
the taker-taker rows (rt 11); the MM tiers change the constant, not the shape.

Usage: python scripts/_s54_backfill_sweep.py [--bins-dir /tmp/backfill]
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_flip_threshold import rolling_range_bps, bracket_outcome, RANGE_W, BRACKET_FRAC, NOTIONAL  # noqa: E402
from odcore.flip_detector import lean_series, detect_flips  # noqa: E402
from odcore.swing_bigline import run_bigline_adaptive   # noqa: E402

BINS_DIR = "/tmp/backfill"
COINS = [("sol", "SOLUSDT"), ("eth", "ETHUSDT"), ("btc", "BTCUSDT"),
         ("doge", "DOGEUSDT"), ("xrp", "XRPUSDT")]
TK = 5.5
SCALES = [(1800, 0.3), (1800, 0.5), (3600, 0.3), (3600, 0.5), (7200, 0.5)]
KS = [0.0, 0.04, 0.09]
FIXED_AD = (0.25, 4.0)
N_SHUF = 2
WEEK_S = 7 * 24 * 3600


def load_bins(path):
    """bins dict {ts: {buy,sell,mid,...}} -> uniform 1-sec arrays (ffill mid, zero flow)."""
    with open(path) as f:
        d = json.load(f)
    ts = np.array(sorted(float(k) for k in d.keys()))
    t0, t1 = ts[0], ts[-1]
    n = int(t1 - t0) + 1
    mid = np.zeros(n)
    buy = np.zeros(n)
    sell = np.zeros(n)
    have = np.zeros(n, bool)
    for k, v in d.items():
        i = int(float(k) - t0)
        mid[i] = v["mid"]
        buy[i] = v["buy"]
        sell[i] = v["sell"]
        have[i] = True
    # forward-fill mid
    idx = np.where(have, np.arange(n), 0)
    np.maximum.accumulate(idx, out=idx)
    mid = mid[idx]
    first = np.argmax(have)
    mid[:first] = mid[first]
    return mid, buy, sell, float(have.mean()), n / 3600.0


def sweep_cell(coin, mid, buy, sell, hrs):
    rng4 = rolling_range_bps(mid, RANGE_W)
    rt = 2 * TK
    out = {}
    for (W, rev) in SCALES:
        lean = lean_series(buy, sell, W)
        flips, _ = detect_flips(lean, rev)
        flips = [(int(c), int(p), int(s)) for (c, p, s) in flips if c > RANGE_W // 4]
        srow = dict(n_flips=len(flips), flips_day=len(flips) / hrs * 24.0, k={})
        for k in KS:
            acted = real = 0
            pnl = []
            for (c, p, s) in flips:
                rng = rng4[c]
                if rng <= 0:
                    continue
                t_act = None
                if k == 0.0:
                    t_act = c
                else:
                    xthr = k * rng / 1e4
                    base = mid[c]
                    horizon = min(len(mid), c + RANGE_W)
                    for t in range(c + 1, horizon):
                        if s * (mid[t] - base) / base >= xthr:
                            t_act = t
                            break
                if t_act is None:
                    continue
                b = bracket_outcome(mid, t_act, s, BRACKET_FRAC * rng4[t_act])
                if b is None:
                    continue
                acted += 1
                real += int(b[0])
                pnl.append(b[1] - rt)
            srow["k"][f"{k:.2f}"] = dict(
                acted=acted, n_real=real,
                p_real=(real / acted) if acted else None,
                net_leg=float(np.mean(pnl)) if pnl else None,
                dhr=float(np.sum(pnl) / 1e4 * NOTIONAL / hrs) if pnl else 0.0,
                pnl=[float(x) for x in pnl])
        out[f"W{W}_r{rev:.2f}"] = srow
    return out


def bigline_cell(coin, mid, hrs):
    rt = 2 * TK
    res = {}
    legs = run_bigline_adaptive(mid, FIXED_AD[0], int(FIXED_AD[1] * 3600))
    gross = np.asarray([l.gross_bps for l in legs])
    if len(gross):
        res["full"] = dict(n=len(gross), gross_leg=float(gross.mean()),
                           net_leg=float((gross - rt).mean()),
                           dhr=float((gross - rt).sum() / 1e4 * NOTIONAL / hrs),
                           dhr_rev=float((-gross - rt).sum() / 1e4 * NOTIONAL / hrs),
                           win=float((gross > 0).mean()))
        vals = []
        for s in range(N_SHUF):
            rng = np.random.default_rng(2000 + s)
            r = np.diff(np.log(mid))
            m2 = float(mid[0]) * np.exp(np.concatenate([[0.0], np.cumsum(rng.permutation(r))]))
            g2 = [l.gross_bps for l in run_bigline_adaptive(m2, FIXED_AD[0], int(FIXED_AD[1] * 3600))]
            vals.append(float((np.asarray(g2) - rt).sum() / 1e4 * NOTIONAL / hrs) if g2 else 0.0)
        res["full"]["shuffle_dhr"] = float(np.mean(vals))
    # per-week splits — the multi-window gate
    nW = max(1, int(len(mid) // WEEK_S))
    res["weeks"] = []
    for w in range(nW):
        sl = slice(w * WEEK_S, min(len(mid), (w + 1) * WEEK_S))
        m_w = mid[sl]
        if len(m_w) < 12 * 3600:
            continue
        h_w = len(m_w) / 3600.0
        legs_w = run_bigline_adaptive(m_w, FIXED_AD[0], int(FIXED_AD[1] * 3600))
        g_w = np.asarray([l.gross_bps for l in legs_w])
        res["weeks"].append(dict(
            n=len(g_w),
            dhr=float((g_w - rt).sum() / 1e4 * NOTIONAL / h_w) if len(g_w) else 0.0))
    return res


def main():
    bins_dir = BINS_DIR
    if "--bins-dir" in sys.argv:
        bins_dir = sys.argv[sys.argv.index("--bins-dir") + 1]
    results = []
    for (coin, sym) in COINS:
        path = os.path.join(bins_dir, f"{sym}_30d_bins.json")
        if not os.path.exists(path):
            print(f"[{coin}] no bins at {path} — skipped")
            continue
        mid, buy, sell, cover, hrs = load_bins(path)
        r = dict(cell=f"{coin}_bybit_perp", hrs=hrs, coverage=cover)
        print(f"\n== {r['cell']} ({hrs:.0f}h, coverage {cover:.1%}) ==")
        r["bell"] = sweep_cell(coin, mid, buy, sell, hrs)
        for sname, srow in r["bell"].items():
            k0 = srow["k"]["0.00"]
            pr = "n/a" if k0["p_real"] is None else f"{k0['p_real']:.3f}"
            print(f"  BELL {sname}: {srow['n_flips']} flips ({srow['flips_day']:.1f}/day) "
                  f"k=0: P(real) {pr}  net/leg {k0['net_leg']:+.1f}  ${k0['dhr']:+.2f}/hr")
        r["bigline"] = bigline_cell(coin, mid, hrs)
        f = r["bigline"].get("full")
        if f:
            wk = [w["dhr"] for w in r["bigline"]["weeks"]]
            print(f"  BIGLINE f0.25/w4h: n={f['n']} net/leg {f['net_leg']:+.1f} "
                  f"${f['dhr']:+.2f}/hr (rev {f['dhr_rev']:+.2f}, shuf {f['shuffle_dhr']:+.2f}) "
                  f"weeks: {['%+.2f' % v for v in wk]}")
        results.append(r)

    # pooled bell
    print(f"\n== POOLED BELL ({len(results)} bybit_perp cells) ==")
    print("    scale        k    acted  P(real)   net/leg   $/hr-equiv")
    tot_hrs = sum(r["hrs"] for r in results)
    for sname in results[0]["bell"].keys() if results else []:
        for k in KS:
            pnl = []
            real = 0
            for r in results:
                row = r["bell"].get(sname, {}).get("k", {}).get(f"{k:.2f}")
                if row and row.get("pnl"):
                    pnl += row["pnl"]
                    real += row["n_real"]
            if not pnl:
                continue
            p = real / len(pnl)
            z = (p - 0.5) * np.sqrt(len(pnl)) / 0.5
            print(f"    {sname:<11} {k:.2f}  {len(pnl):>6}   {p:.3f} (z={z:+.1f})"
                  f"  {np.mean(pnl):>+7.1f}   {np.sum(pnl)/1e4*NOTIONAL/tot_hrs:>+7.2f}")

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "_s54_backfill_sweep_results.json")
    with open(out, "w") as f:
        for r in results:                      # strip bulky pnl lists from the saved JSON
            for srow in r["bell"].values():
                for krow in srow["k"].values():
                    krow.pop("pnl", None)
        json.dump(results, f, indent=1)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
