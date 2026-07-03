"""_s54_zz_entry_bigline_exit.py — Greg's S54 hybrid: SAME zigzag entries, BIG LINE exit.

"we want to use our same entry strategy from zig zag so let's clone that. it's our exit that we
want to deploy the big line on."

The controlled experiment: identical entry stream (the deployed fine-scale flip machinery,
cloned not modified), two exit engines:
  A. ZIGZAG exit  — exit/flip at the next opposite flip confirm (today's one-shot behavior).
  B. BIG LINE exit — hold; initial stop flat at the entry turn's extreme; adaptive-scale pivots
     ratchet the trendline under/over the move; exit on the line break (ride_from_entries).
Any difference in $/hr is purely the exit engine.

Entry streams (both reported, neither tuned):
  - lean0.10 : detect_flips(lean_series(buy,sell,60s), REV=0.1) — the deployed detector on 1-sec.
  - zzfine   : causal price zigzag at theta = 4 x (half_spread + taker) — the S36b fee-floor scale.
Fills: taker both ends (rt_taker) + the mk-1-entry tier in the JSON. Controls per row: REVERSED
(fade every leg) and joint price+flow SHUFFLE (3 seeds). Splits: window halves. No gates, no
per-cell tuning; adaptive line params fixed = (frac 0.25, window 4h), eps = theta/6, clip 15-120.

Usage: python scripts/_s54_zz_entry_bigline_exit.py [--leakage]
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                      # noqa: E402
from _liquidity_dive import build_channels, median_spread_bps  # noqa: E402
from _capacity_model import FLOW_W                      # noqa: E402
from _s52_accum_vs_oneshot import _price_zigzag, ZIG_K  # noqa: E402  (cloned entry, not copied)
from _s54_bigline_probe import CELLS, DEC, LEAN_W_1S, FIXED_AD, NOTIONAL  # noqa: E402
from odcore.flip_detector import lean_series, detect_flips  # noqa: E402
from odcore.swing_bigline import ride_from_entries      # noqa: E402
from odcore.leakage import assert_no_leakage            # noqa: E402

LEAN_REV = 0.10
N_SHUF = 3


def _legs_zz_exit(mid, entries):
    """Exit A: always-flip at the next confirm (deployed one-shot shape). gross bps per leg."""
    out = []
    for a, b in zip(entries[:-1], entries[1:]):
        ci, s = int(a[0]), int(a[2])
        cj = int(b[0])
        out.append((s, ci, cj, s * (mid[cj] - mid[ci]) / mid[ci] * 1e4))
    return out


def _stats(gross, holds_h, hrs, rt_fees, extra=None):
    gross = np.asarray(gross, float)
    if not len(gross):
        return dict(n_legs=0)
    rows = {}
    for lbl, rt in rt_fees.items():
        net = gross - rt
        rows[lbl] = dict(net_leg=float(net.mean()),
                         dhr=float(net.sum() / 1e4 * NOTIONAL / hrs),
                         dhr_rev=float((-gross - rt).sum() / 1e4 * NOTIONAL / hrs))
    d = dict(n_legs=len(gross), gross_leg=float(gross.mean()), win=float((gross > 0).mean()),
             med_hold_h=float(np.median(holds_h)), rows=rows)
    if extra:
        d.update(extra)
    return d


def _run_streams(mid, buy1, sell1, hs, tk):
    lean = lean_series(buy1, sell1, LEAN_W_1S)
    theta_f = ZIG_K * (hs + tk)
    streams = {}
    fl, _ = detect_flips(lean, LEAN_REV)
    streams["lean0.10"] = [(c, p, s) for (c, p, s) in fl]
    streams[f"zz{theta_f:.0f}bp"] = _price_zigzag(mid, theta_f)
    return streams


def run_cell(cell, path, K, tk):
    if not os.path.exists(path):
        return None
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)[::DEC]
    buy0 = np.asarray(g["buy"], float)
    sell0 = np.asarray(g["sell"], float)
    n10 = (len(buy0) // DEC) * DEC
    buy1 = buy0[:n10].reshape(-1, DEC).sum(1)
    sell1 = sell0[:n10].reshape(-1, DEC).sum(1)
    L = min(len(mid), len(buy1))
    mid, buy1, sell1 = mid[:L], buy1[:L], sell1[:L]
    hs = median_spread_bps(path, raw=raw) / 2.0
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    rt_fees = {"rt_taker": 2 * tk, "rt_mk-1": -1.0 + tk}
    out = dict(cell=cell, hrs=hrs, streams={}, splits={})

    streams = _run_streams(mid, buy1, sell1, hs, tk)
    for sname, ent in streams.items():
        if len(ent) < 4:
            out["streams"][sname] = dict(n_entries=len(ent))
            continue
        # exit A: flip at next confirm
        zzlegs = _legs_zz_exit(mid, ent)
        A = _stats([l[3] for l in zzlegs], [(l[2] - l[1]) / 3600.0 for l in zzlegs], hrs, rt_fees)
        # exit B: big line trail
        bl = ride_from_entries(mid, ent, FIXED_AD[0], int(FIXED_AD[1] * 3600))
        B = _stats([l.gross_bps for l in bl], [l.hold_cells / 3600.0 for l in bl], hrs, rt_fees,
                   extra=dict(exposure=float(sum(l.hold_cells for l in bl)) / len(mid),
                              n_forced=int(sum(l.forced for l in bl)),
                              rides_taken=len(bl), entries_offered=len(ent)))
        # joint shuffle control for B
        vals = []
        for s in range(N_SHUF):
            rng = np.random.default_rng(1000 + s)
            r = np.diff(np.log(mid))
            perm = rng.permutation(len(r))
            m2 = float(mid[0]) * np.exp(np.concatenate([[0.0], np.cumsum(r[perm])]))
            b2 = np.concatenate([[buy1[0]], buy1[1:][perm]])
            s2 = np.concatenate([[sell1[0]], sell1[1:][perm]])
            st2 = _run_streams(m2, b2, s2, hs, tk)[sname]
            bl2 = ride_from_entries(m2, st2, FIXED_AD[0], int(FIXED_AD[1] * 3600)) if len(st2) >= 4 else []
            g2 = [l.gross_bps for l in bl2]
            vals.append(float((np.asarray(g2) - rt_fees["rt_taker"]).sum() / 1e4 * NOTIONAL / hrs)
                        if g2 else 0.0)
        B["shuffle_dhr"] = float(np.mean(vals))
        out["streams"][sname] = dict(n_entries=len(ent), zz_exit=A, bigline_exit=B)

    # halves, both exits, both streams
    bounds = np.linspace(0, len(mid), 3).astype(int)
    for w in range(2):
        sl = slice(bounds[w], bounds[w + 1])
        m_w, b_w, s_w = mid[sl], buy1[sl], sell1[sl]
        h_w = hrs / 2
        row = {}
        for sname, ent in _run_streams(m_w, b_w, s_w, hs, tk).items():
            if len(ent) < 4:
                continue
            zz = _legs_zz_exit(m_w, ent)
            bl = ride_from_entries(m_w, ent, FIXED_AD[0], int(FIXED_AD[1] * 3600))
            row[sname] = dict(
                zz=_stats([l[3] for l in zz], [1], h_w, rt_fees),
                bl=_stats([l.gross_bps for l in bl], [1], h_w, rt_fees))
        out["splits"][f"W{w+1}"] = row
    return out


def leakage_gate():
    (cell, path, K, tk) = CELLS[0]
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)[::DEC][:40_000]
    buy0 = np.asarray(g["buy"], float)
    sell0 = np.asarray(g["sell"], float)
    n10 = (len(buy0) // DEC) * DEC
    buy1 = buy0[:n10].reshape(-1, DEC).sum(1)[:len(mid)]
    sell1 = sell0[:n10].reshape(-1, DEC).sum(1)[:len(mid)]
    ts = np.arange(len(mid), dtype=float)
    rng = np.random.default_rng(5)
    idxs = np.sort(rng.integers(5_000, len(mid) - 1, size=12))

    def sig(i, ts_, p, bv, sv):
        j = int(i) + 1
        sub = np.asarray(p[:j], float)
        lb = lean_series(np.asarray(bv[:j], float), np.asarray(sv[:j], float), LEAN_W_1S)
        fl, _ = detect_flips(lb, LEAN_REV)
        legs = ride_from_entries(sub, fl, FIXED_AD[0], int(FIXED_AD[1] * 3600))
        if not legs:
            return 0
        return int(legs[-1].side) if legs[-1].forced else 0

    ok, fails = assert_no_leakage(sig, ts, mid, buy1, sell1, idxs, reps=2)
    print(f"# LEAKAGE GATE (zz-entry + bigline-exit, sol prefix, {len(idxs)} idxs): "
          f"{'PASS' if ok else 'FAIL'} ({len(fails)} fails)")
    return ok


def main():
    if "--leakage" in sys.argv:
        leakage_gate()
        return
    if not leakage_gate():
        print("!! leakage FAIL — not running")
        return
    results = []
    for (cell, path, K, tk) in CELLS:
        r = run_cell(cell, path, K, tk)
        if r is None:
            continue
        results.append(r)
        print(f"\n== {cell} ({r['hrs']:.1f}h) ==")
        print("  stream        entries |exitA(zz):  n  net/leg   $/hr | exitB(LINE):  n  net/leg"
              "   $/hr   rev$/hr  shuf$/hr  expo medhold")
        for sname, s in r["streams"].items():
            if "zz_exit" not in s:
                print(f"  {sname:<13} {s['n_entries']:>6}  (too few entries)")
                continue
            A, B = s["zz_exit"], s["bigline_exit"]
            a = A["rows"]["rt_taker"]; b = B["rows"]["rt_taker"]
            print(f"  {sname:<13} {s['n_entries']:>6} |{A['n_legs']:>10}  {a['net_leg']:>+7.1f}"
                  f"  {a['dhr']:>+6.2f} |{B['rides_taken']:>11}  {b['net_leg']:>+7.1f}"
                  f"  {b['dhr']:>+6.2f}  {b['dhr_rev']:>+7.2f}  {B['shuffle_dhr']:>+7.2f}"
                  f"  {B['exposure']:>4.0%} {B['med_hold_h']:>5.2f}h")
        for w, row in r["splits"].items():
            parts = []
            for sname, d in row.items():
                za = d["zz"].get("rows", {}).get("rt_taker", {}).get("dhr")
                ba = d["bl"].get("rows", {}).get("rt_taker", {}).get("dhr")
                parts.append(f"{sname}: zz {za:+.2f} vs LINE {ba:+.2f}"
                             if za is not None and ba is not None else f"{sname}: thin")
            print(f"  {w}: " + "   ".join(parts))

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "_s54_zz_entry_bigline_exit_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=1)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
