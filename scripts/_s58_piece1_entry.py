"""_s58_piece1_entry.py — S58 PIECE 1: THE ENTRY (kickoff job 1; one defined test).

Question: at mid-band scale (theta 60/80/100), does the ARMED FINE-CONFIRM entry — the fine
flip anchored NEAREST THE PIVOT (leg extension >= theta arms; the first c*theta reversal off
the running extreme confirms; optional R4 dipole veto on `continue`-class dips) — beat the
theta-confirm baseline entry at REAL fee models?

This is the S57 bleed fix aimed where the handoff points: S57's mid-band probe entered at the
first fine flip AFTER the coarse theta-confirm and measured -31bp/leg gross theta-giveback
(SOL, REVERSED positive). Here the entry is the confirm of the armed zigzag itself — ~c*theta
from the pivot instead of theta+ (the S55 R5 lag cut, 151bp -> 26bp). S56's ARM-family kill
was graded under the (now banned) Bybit rebate regime with FIXED fine=25bp; at real fees with
the confirm threshold SCALING WITH THE BAND (S57 lesson: +2bp confirms everything = no filter)
the question changed — this is the legitimate re-test, not a relitigation.

Machines (identical scoring mechanics, always-in-market flip machine, mid fills at confirms):
  base    : plain theta zigzag — flips at theta-confirm (the S55 R14 "structurally
            unharvestable" arm; the baseline).
  armed   : armed_fine_zigzag_v2 (S56) — extremes anchored since last flip, ARM=theta arms,
            first c*theta reversal off the extreme confirms, trailing-ARM fallback bounds loss.
  armed+V : same + R4 dipole veto — a fine dip only confirms if the causal S36 divergence()
            read at the pivot candidate is NOT `continue`-class (S55 R4: continue/rc~0 = the
            false-fire class); the trailing fallback is never vetoed (loss stays bounded).

Fees (S57 standing models, maker-posted both sides -> fee/leg = 2*maker; taker exposure at
deployed mechanics measured 0-5%, noted not modeled): cb_entry 40 | cb_early 10 | cb_real 8 |
cb_scale 3 | cb_top 0 (ceiling only, never held).

Controls (kickoff-mandatory):
  REVERSED  — sides inverted, same mechanics (under mid scoring gross exactly negates; the
              informative shape is REV net at cb_real: a real edge shows fwd >> REV).
  SHUFFLE   — per-second log-returns permuted (fixed seeds), mid rebuilt, WHOLE pipeline
              re-run (structure-free tape floor), on cb_real-positive cells.
  PER-WEEK  — weekly (bins) / daily (books) net-$ splits at cb_real: positive fraction + z.
  LEAKAGE   — truncation invariance: flips computed on a prefix tape must equal the full-tape
              flips below the cut (causality by construction, asserted not assumed).

Windows: 30d x 5-coin Binance spot bins (research tape — trade venue remains Coinbase) +
the 5-coin Coinbase books. Never promote a grid point off its curve; renders read with Greg.

Usage:
  python scripts/_s58_piece1_entry.py --venue bins        # 30d Binance spot sweep
  python scripts/_s58_piece1_entry.py --venue books       # Coinbase books sweep
  python scripts/_s58_piece1_entry.py --venue bins --gate # + shuffle/week/leakage on survivors
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _s54_backfill_sweep import load_bins, COINS                     # noqa: E402
from _s56_armed_gate import armed_fine_zigzag_v2                     # noqa: E402
from _s57_midband_probe import coarse_zigzag                         # noqa: E402
from odcore.info_dipole import divergence                            # noqa: E402

CAP = 5000.0
THETAS = (60.0, 80.0, 100.0)
CFRACS = (0.125, 0.25, 0.5)
FEES = (("cb_entry", 40.0), ("cb_early", 10.0), ("cb_real", 8.0),
        ("cb_scale", 3.0), ("cb_top", 0.0))
CB_REAL = 8.0
DIVW = 600
N_SHUF = 3
WEEK_S = 7 * 24 * 3600
DAY_S = 24 * 3600


def armed_fine_zigzag_v2_veto(mid, buy, sell, arm_bp, fine_bp, divw=DIVW):
    """S56 v2 arming + the R4 `continue`-class veto (kickoff spec: veto ONLY the known-worst
    class; a vetoed dip keeps riding; the trailing-ARM fallback is never vetoed)."""
    a, f = arm_bp / 1e4, fine_bp / 1e4
    n = len(mid)
    flips = []
    lo_i = hi_i = 0
    mode = 0
    cache = {}

    def gate_ok(pi):
        if pi in cache:
            return cache[pi]
        lo = max(0, pi - divw)
        dv = None
        if pi - lo >= 12:
            dv = divergence(buy[lo:pi + 1], sell[lo:pi + 1], float(mid[pi] - mid[lo]))
        ok = (dv is None) or dv["expect"] != "continue"
        cache[pi] = ok
        return ok

    for t in range(1, n):
        m = mid[t]
        if m < mid[lo_i]:
            lo_i = t
        if m > mid[hi_i]:
            hi_i = t
        if mode >= 0:
            armed = mid[hi_i] >= mid[lo_i] * (1 + a)
            if armed and m <= mid[hi_i] * (1 - f) and gate_ok(hi_i):
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
            if mode == 1 and m <= mid[hi_i] * (1 - a):      # trailing fallback — never vetoed
                flips.append((t, hi_i, -1)); mode = -1; lo_i = t
                continue
        if mode <= 0:
            armed = mid[lo_i] <= mid[hi_i] * (1 - a)
            if armed and m >= mid[lo_i] * (1 + f) and gate_ok(lo_i):
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
                continue
            if mode == -1 and m >= mid[lo_i] * (1 + a):     # trailing fallback
                flips.append((t, lo_i, +1)); mode = +1; hi_i = t
    return flips


def score(mid, flips, hrs):
    """Always-in-market flip machine on mid fills: leg k = flips[k].confirm -> flips[k+1].confirm.
    Returns dict with per-leg arrays (gross bp, entry confirm idx) + rates."""
    if len(flips) < 2:
        return None
    ci = np.asarray([int(c) for (c, p, s) in flips])
    sd = np.asarray([int(s) for (c, p, s) in flips])
    ep = mid[ci[:-1]]
    xp = mid[ci[1:]]
    gross = sd[:-1] * (xp - ep) / ep * 1e4
    return {"gross": gross, "ei": ci[:-1], "n": len(gross), "lph": len(gross) / hrs,
            "hrs": hrs}


def net_dollars_hr(res, mk_bp):
    fee = 2.0 * mk_bp
    return float(np.sum(CAP * (res["gross"] - fee) / 1e4)) / res["hrs"]


def run_grid(tag, mid, buy, sell, hrs, quiet=False):
    """All machines x theta x c on one tape. Returns {(machine, theta, c): res}."""
    out = {}
    for theta in THETAS:
        # coarse_zigzag returns (pivot, confirm, side) — normalize to (confirm, pivot, side)
        fl = [(c, p, s) for (p, c, s) in coarse_zigzag(mid, theta)]
        out[("base", theta, 0.0)] = score(mid, fl, hrs)
        for c in CFRACS:
            fine = c * theta
            fl = armed_fine_zigzag_v2(mid, theta, fine)
            out[("armed", theta, c)] = score(mid, fl, hrs)
            fl = armed_fine_zigzag_v2_veto(mid, buy, sell, theta, fine)
            out[("armedV", theta, c)] = score(mid, fl, hrs)
    if not quiet:
        print(f"\n=== {tag} ({hrs:.1f}h) — net $/hr @$5k flat, maker both sides ===")
        hdr = (f"{'machine':>7} {'th':>4} {'c':>5} | {'legs/h':>6} {'gross/leg':>9} "
               f"{'win%':>5} |" + "".join(f"{lbl:>9}" for (lbl, _) in FEES) + f" | {'REV@real':>8}")
        print(hdr)
        for (m, theta, c), res in out.items():
            if res is None:
                print(f"{m:>7} {theta:>4.0f} {c:>5.3f} | (no legs)")
                continue
            cols = "".join(f"{net_dollars_hr(res, mk):>+9.2f}" for (_, mk) in FEES)
            rev = float(np.sum(CAP * (-res['gross'] - 2 * CB_REAL) / 1e4)) / res["hrs"]
            print(f"{m:>7} {theta:>4.0f} {c:>5.3f} | {res['lph']:>6.2f} "
                  f"{np.mean(res['gross']):>+9.2f} {100 * np.mean(res['gross'] > 0):>5.0f} |"
                  f"{cols} | {rev:>+8.2f}")
    return out


def shuffle_mid(mid, rng):
    """Permute per-second log-returns, rebuild the path from the same start."""
    lr = np.diff(np.log(mid))
    rng.shuffle(lr)
    return mid[0] * np.exp(np.concatenate([[0.0], np.cumsum(lr)]))


def week_split(res, sec_per_bucket):
    """Bucketed net-$ at cb_real by entry index (relative weeks on bins / days on books)."""
    fee = 2.0 * CB_REAL
    dollars = CAP * (res["gross"] - fee) / 1e4
    b = (res["ei"] // sec_per_bucket).astype(int)
    sums = np.bincount(b, weights=dollars)
    keep = np.bincount(b) > 0
    return sums[keep]


def leakage_check(mid, buy, sell, theta=80.0, c=0.25):
    """Truncation invariance: flips on a prefix must equal full-tape flips below the cut."""
    full = armed_fine_zigzag_v2_veto(mid, buy, sell, theta, c * theta)
    n = len(mid)
    for cut in (n // 3, n // 2, (3 * n) // 4):
        pre = armed_fine_zigzag_v2_veto(mid[:cut], buy[:cut], sell[:cut], theta, c * theta)
        want = [f for f in full if f[0] < cut]
        if pre[:len(want)] != want:
            return False
    return True


def load_venue(venue):
    """Yields (coin, mid, buy, sell, hrs, bucket_s)."""
    if venue == "bins":
        for (coin, sym) in COINS:
            p = f"/tmp/backfill/{sym}_30d_bins.json"
            if not os.path.exists(p):
                print(f"[{coin}] bins missing — re-pull per kickoff"); continue
            mid, buy, sell, cover, hrs = load_bins(p)
            yield coin, np.asarray(mid, float), np.asarray(buy, float), \
                np.asarray(sell, float), hrs, WEEK_S
    else:
        from _birth_probe import load_book
        from _liquidity_dive import build_channels
        from odcore.platform import FLOW_W
        for coin in ("sol", "eth", "btc", "doge", "xrp"):
            p = f"/tmp/{coin}_coinbase_book.jsonl.gz"
            if not os.path.exists(p):
                print(f"[{coin}] book missing"); continue
            raw = load_book(p)
            _, g = build_channels(p, 1, FLOW_W, raw=raw)
            mid = np.asarray(g["mid"], float)
            buy, sell = np.asarray(g["buy"], float), np.asarray(g["sell"], float)
            hrs = (float(raw["ts"][-1]) - float(raw["ts"][0])) / 3600.0
            yield coin, mid, buy, sell, hrs, DAY_S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", choices=("bins", "books"), default="bins")
    ap.add_argument("--gate", action="store_true",
                    help="shuffle + per-week + leakage on cb_real-positive cells")
    args = ap.parse_args()

    grids = {}
    tapes = {}
    for coin, mid, buy, sell, hrs, bucket in load_venue(args.venue):
        grids[coin] = run_grid(f"{coin} {args.venue}", mid, buy, sell, hrs)
        tapes[coin] = (mid, buy, sell, hrs, bucket)

    if not args.gate:
        return

    print("\n#### GATE (cb_real-positive cells) ####")
    for coin, grid in grids.items():
        mid, buy, sell, hrs, bucket = tapes[coin]
        ok = leakage_check(mid, buy, sell)
        print(f"\n[{coin}] leakage truncation-invariance: {'PASS' if ok else 'FAIL'}")
        for key, res in grid.items():
            if res is None or key[0] == "base":
                continue
            fwd = net_dollars_hr(res, CB_REAL)
            if fwd <= 0:
                continue
            m, theta, c = key
            # shuffle floor: full pipeline on return-permuted tapes
            sh = []
            for si in range(N_SHUF):
                rng = np.random.default_rng(1000 + si)
                smid = shuffle_mid(mid, rng)
                if m == "armedV":
                    sfl = armed_fine_zigzag_v2_veto(smid, buy, sell, theta, c * theta)
                else:
                    sfl = armed_fine_zigzag_v2(smid, theta, c * theta)
                sres = score(smid, sfl, hrs)
                sh.append(net_dollars_hr(sres, CB_REAL) if sres else 0.0)
            sh = np.asarray(sh)
            wk = week_split(res, bucket)
            zw = float(np.mean(wk) / (np.std(wk, ddof=1) / np.sqrt(len(wk)))) if len(wk) > 1 else 0.0
            print(f"  {m} th{theta:.0f} c{c:.3f}: fwd {fwd:+.2f}/hr | shuffle "
                  f"{np.mean(sh):+.2f}±{np.std(sh):.2f} | weeks {np.sum(wk > 0)}/{len(wk)} "
                  f"pos z={zw:+.1f}")


if __name__ == "__main__":
    main()
