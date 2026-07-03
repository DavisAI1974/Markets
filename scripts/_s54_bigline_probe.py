"""_s54_bigline_probe.py — S54 JOB 1: the BIG-TRENDS thread. Oracle at coarse theta + the BIG LINE
strategy (Greg's trendline ride/break, odcore/swing_bigline.py) head-to-head vs the coarse causal
zigzag flip. New files only — the deployed zigzag/one-shot/accum code paths are untouched.

Design decisions FIXED before running (never tune off one window):
  - Everything runs on a 1-SECOND decimated mid (mid[::10]). At theta >= 30bps and multi-hour holds,
    100ms resolution adds nothing but cost; 1-sec is the S39 standard for swing-scale work.
  - Fills are TAKER at entry and exit (mid at signal time, taker fee both ends). No queue model at
    all -> the Q1 honest-queue problem does not apply to this thread by construction. RT fee tiers
    reported: rt10 = tk5+tk5 Coinbase (rt11 Bybit), rt4 = mk-1 entry + tk5 exit (optimistic label).
  - Oracle theta sweep: 60/100/150/250 bps (kickoff). Causal zigzag flip at the same thetas.
  - Big line grid: theta_pivot in {30,60,100} x break_eps in {5,10} bps — all cells reported, none
    selected. The FIXED walkthrough/render/split config is tp60/eps10, chosen here, in advance.
  - Controls on every strategy row: shuffle (3 seeds, permuted 1-sec log-returns, path rebuilt) and
    REVERSED (same legs, opposite side). Leakage gate on the big-line position signal (SOL prefix).
  - Window splits: halves on every cell, quarters on BTC (196h) — fixed config only.

Usage: python scripts/_s54_bigline_probe.py            (all cells -> _s54_bigline_results.json)
       python scripts/_s54_bigline_probe.py --leakage  (leakage gate only, SOL)
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
from _s52_accum_vs_oneshot import _price_zigzag         # noqa: E402  (reused, not copied)
from odcore.swing_bigline import run_bigline, run_bigline_adaptive, position_signal_at  # noqa: E402
from odcore.flip_detector import lean_series            # noqa: E402  (S40 causal flow lean)
from odcore.leakage import assert_no_leakage            # noqa: E402

CELLS = [
    # (cell, path, K, taker_bps)
    ("sol_coinbase",  "/tmp/sol_coinbase_book.jsonl.gz",  1, 5.0),
    ("eth_coinbase",  "/tmp/eth_coinbase_book.jsonl.gz",  1, 5.0),
    ("btc_coinbase",  "/tmp/btc_coinbase_book.jsonl.gz", 10, 5.0),
    ("doge_coinbase", "/tmp/doge_coinbase_book.jsonl.gz", 1, 5.0),
    ("xrp_coinbase",  "/tmp/xrp_coinbase_book.jsonl.gz",  1, 5.0),
    ("sol_bybit",     "/tmp/sol_bybit_book.jsonl.gz",     1, 5.5),
    ("eth_bybit",     "/tmp/eth_bybit_book.jsonl.gz",     1, 5.5),
]
ORACLE_THETAS = [60.0, 100.0, 150.0, 250.0]
BL_GRID = [(tp, eps) for tp in (30.0, 60.0, 100.0) for eps in (5.0, 10.0)]
FIXED_BL = (60.0, 10.0)      # walkthrough/split/render config — fixed in advance
FIXED_ZZ = 100.0
# Adaptive scale (Greg: "when it gets choppier, scale the lines down" — no zigzag fallback):
# theta = frac x trailing hi-lo range over W hours, clip [15,120]bps, eps = theta/6.
AD_GRID = [(frac, wh) for frac in (0.15, 0.25) for wh in (4.0, 8.0)]
FIXED_AD = (0.25, 4.0)       # walkthrough/split/render config — fixed in advance
# Dipole-flip fast confirm (Greg: "for the bounce back you want the dipole flip + (x_price)"):
# pivot also confirms at bounce >= X_FRAC*theta when the trailing flow lean has flipped sign.
# XONLY = same cheaper bounce WITHOUT the flow requirement — the honesty ablation.
X_FRAC = 0.5
LEAN_W_1S = 60               # = WFLIP 600 x 100ms cells, on the 1-sec grid
NOTIONAL = 5_000.0
N_SHUF = 3
DEC = 10                     # 100ms -> 1-sec


def _shuffled_path(mid, seed):
    r = np.diff(np.log(mid))
    rng = np.random.default_rng(seed)
    return float(mid[0]) * np.exp(np.concatenate([[0.0], np.cumsum(rng.permutation(r))]))


def _oracle(mid, hrs, theta, rt_fees):
    flips = _price_zigzag(mid, theta)
    if len(flips) < 2:
        return dict(n_swings=len(flips), swings_day=0.0, med_swing=None, net_day={})
    sw = [abs(mid[int(b[1])] - mid[int(a[1])]) / mid[int(a[1])] * 1e4
          for a, b in zip(flips[:-1], flips[1:])]           # pivot-to-pivot, perfect prices
    days = hrs / 24.0
    out = dict(n_swings=len(sw), swings_day=len(sw) / days, med_swing=float(np.median(sw)),
               net_day={})
    for lbl, rt in rt_fees.items():
        out["net_day"][lbl] = float(sum(s - rt for s in sw) / 1e4 * NOTIONAL / days)
    return out


def _zigzag_flip(mid, hrs, theta, rt_fees):
    """Causal always-in-market flip at confirm prices; leg = confirm to next confirm."""
    flips = _price_zigzag(mid, theta)
    if len(flips) < 3:
        return dict(n_legs=max(0, len(flips) - 1), rows={})
    gross = []
    for a, b in zip(flips[:-1], flips[1:]):
        ci, _pi, side = int(a[0]), int(a[1]), int(a[2])
        cj = int(b[0])
        gross.append(side * (mid[cj] - mid[ci]) / mid[ci] * 1e4)
    gross = np.asarray(gross)
    rows = {}
    for lbl, rt in rt_fees.items():
        net = gross - rt
        rows[lbl] = dict(net_leg=float(net.mean()), dhr=float(net.sum() / 1e4 * NOTIONAL / hrs),
                         dhr_rev=float((-gross - rt).sum() / 1e4 * NOTIONAL / hrs))
    return dict(n_legs=len(gross), gross_leg=float(gross.mean()),
                win=float((gross > 0).mean()), rows=rows)


def _bigline(mid, hrs, tp, eps, rt_fees, cell_s=1.0, adaptive=None, align=True,
             lean=None, require_flip=True):
    legs = (run_bigline_adaptive(mid, adaptive[0], int(adaptive[1] * 3600), align=align,
                                 lean=lean, x_frac=X_FRAC, require_flip=require_flip)
            if adaptive else run_bigline(mid, tp, eps, align=align))
    if not legs:
        return dict(n_legs=0)
    gross = np.asarray([l.gross_bps for l in legs])
    hold_h = np.asarray([l.hold_cells * cell_s / 3600.0 for l in legs])
    expo = float(sum(l.hold_cells for l in legs)) / len(mid)
    rows = {}
    for lbl, rt in rt_fees.items():
        net = gross - rt
        rows[lbl] = dict(net_leg=float(net.mean()), dhr=float(net.sum() / 1e4 * NOTIONAL / hrs),
                         dhr_rev=float((-gross - rt).sum() / 1e4 * NOTIONAL / hrs))
    return dict(n_legs=len(legs), gross_leg=float(gross.mean()), win=float((gross > 0).mean()),
                med_hold_h=float(np.median(hold_h)), max_hold_h=float(hold_h.max()),
                exposure=expo, n_forced=int(sum(l.forced for l in legs)),
                n_long=int(sum(1 for l in legs if l.side > 0)), rows=rows)


def _shuffle_dhr(mid, hrs, runner, rt, seeds=range(N_SHUF)):
    vals = []
    for s in seeds:
        m2 = _shuffled_path(mid, 1000 + s)
        r = runner(m2)
        if r is None:
            vals.append(0.0)
            continue
        vals.append(float((np.asarray(r) - rt).sum() / 1e4 * NOTIONAL / hrs) if len(r) else 0.0)
    return float(np.mean(vals))


def run_cell(cell, path, K, tk):
    if not os.path.exists(path):
        print(f"[{cell}] no book")
        return None
    raw = load_book(path)
    ch, g = build_channels(path, K, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)[::DEC]
    buy0 = np.asarray(g["buy"], float)
    sell0 = np.asarray(g["sell"], float)
    n10 = (len(buy0) // DEC) * DEC
    buy1 = buy0[:n10].reshape(-1, DEC).sum(1)       # 1-sec flow (block sums, not sampling)
    sell1 = sell0[:n10].reshape(-1, DEC).sum(1)
    L = min(len(mid), len(buy1))
    mid, buy1, sell1 = mid[:L], buy1[:L], sell1[:L]
    lean = lean_series(buy1, sell1, LEAN_W_1S)
    hs = median_spread_bps(path, raw=raw) / 2.0
    hrs = (raw["ts"][-1] - raw["ts"][0]) / 3600.0
    rt_fees = {"rt_taker": 2 * tk, "rt_mk-1": -1.0 + tk}
    # collection-gap honesty (BTC has a multi-day ffilled hole): constant-mid runs > 10 min
    chg = np.flatnonzero(np.diff(mid) != 0)
    runs = np.diff(np.concatenate([[0], chg + 1, [len(mid)]]))
    gap_hrs = float(runs[runs > 600].sum() / 3600.0)
    out = dict(cell=cell, hrs=hrs, gap_hrs=gap_hrs, spread_bps=2 * hs,
               oracle={}, zigzag={}, bigline={}, splits={})

    for th in ORACLE_THETAS:
        out["oracle"][f"{th:.0f}"] = _oracle(mid, hrs, th, rt_fees)
        z = _zigzag_flip(mid, hrs, th, rt_fees)
        z["shuffle_dhr"] = _shuffle_dhr(
            mid, hrs,
            lambda m2, _t=th: [s * (m2[int(b[0])] - m2[int(a[0])]) / m2[int(a[0])] * 1e4
                               for a, b in zip(_price_zigzag(m2, _t)[:-1], _price_zigzag(m2, _t)[1:])
                               for s in [int(a[2])]],
            rt_fees["rt_taker"])
        out["zigzag"][f"{th:.0f}"] = z

    for (tp, eps) in BL_GRID:
        b = _bigline(mid, hrs, tp, eps, rt_fees)
        b["shuffle_dhr"] = _shuffle_dhr(
            mid, hrs,
            lambda m2, _tp=tp, _e=eps: [l.gross_bps for l in run_bigline(m2, _tp, _e)],
            rt_fees["rt_taker"])
        out["bigline"][f"tp{tp:.0f}_eps{eps:.0f}"] = b
    # v1 unaligned reference at the fixed config — measures Greg's alignment correction
    out["bigline"]["tp60_eps10_UNALIGNED"] = _bigline(mid, hrs, *FIXED_BL, rt_fees, align=False)

    out["adaptive"] = {}
    for (frac, wh) in AD_GRID:
        b = _bigline(mid, hrs, 0, 0, rt_fees, adaptive=(frac, wh))
        b["shuffle_dhr"] = _shuffle_dhr(
            mid, hrs,
            lambda m2, _f=frac, _w=wh: [l.gross_bps
                                        for l in run_bigline_adaptive(m2, _f, int(_w * 3600))],
            rt_fees["rt_taker"])
        out["adaptive"][f"f{frac:.2f}_w{wh:.0f}h"] = b

    # dipole-flip fast confirm + price-only ablation, on the FIXED adaptive config
    for (name, req) in [("DIPOLE", True), ("XONLY", False)]:
        b = _bigline(mid, hrs, 0, 0, rt_fees, adaptive=FIXED_AD, lean=lean, require_flip=req)
        vals = []
        for s in range(N_SHUF):                     # joint shuffle: returns + flow, same perm
            rng = np.random.default_rng(1000 + s)
            r = np.diff(np.log(mid))
            perm = rng.permutation(len(r))
            m2 = float(mid[0]) * np.exp(np.concatenate([[0.0], np.cumsum(r[perm])]))
            b2 = np.concatenate([[buy1[0]], buy1[1:][perm]])
            s2 = np.concatenate([[sell1[0]], sell1[1:][perm]])
            l2 = lean_series(b2, s2, LEAN_W_1S)
            legs2 = run_bigline_adaptive(m2, FIXED_AD[0], int(FIXED_AD[1] * 3600),
                                         lean=l2, x_frac=X_FRAC, require_flip=req)
            g2 = [l.gross_bps for l in legs2]
            vals.append(float((np.asarray(g2) - rt_fees["rt_taker"]).sum() / 1e4 * NOTIONAL / hrs)
                        if g2 else 0.0)
        b["shuffle_dhr"] = float(np.mean(vals))
        out["adaptive"][f"f{FIXED_AD[0]:.2f}_w{FIXED_AD[1]:.0f}h_{name}"] = b

    # window splits — FIXED configs only
    n_split = 4 if hrs > 120 else 2
    bounds = np.linspace(0, len(mid), n_split + 1).astype(int)
    for w in range(n_split):
        sl = slice(bounds[w], bounds[w + 1])
        m_w = mid[sl]
        lean_w = lean_series(buy1[sl], sell1[sl], LEAN_W_1S)
        h_w = hrs / n_split
        out["splits"][f"W{w+1}"] = dict(
            bigline=_bigline(m_w, h_w, *FIXED_BL, rt_fees),
            adaptive=_bigline(m_w, h_w, 0, 0, rt_fees, adaptive=FIXED_AD),
            dipole=_bigline(m_w, h_w, 0, 0, rt_fees, adaptive=FIXED_AD,
                            lean=lean_w, require_flip=True),
            zigzag=_zigzag_flip(m_w, h_w, FIXED_ZZ, rt_fees))
    return out


def leakage_gate():
    path = CELLS[0][1]
    raw = load_book(path)
    ch, g = build_channels(path, CELLS[0][2], FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)[::DEC][:40_000]     # ~11h prefix, cost control
    buy0 = np.asarray(g["buy"], float)
    sell0 = np.asarray(g["sell"], float)
    n10 = (len(buy0) // DEC) * DEC
    buy1 = buy0[:n10].reshape(-1, DEC).sum(1)[:len(mid)]
    sell1 = sell0[:n10].reshape(-1, DEC).sum(1)[:len(mid)]
    ts = np.arange(len(mid), dtype=float)
    dummy = np.zeros(len(mid))
    rng = np.random.default_rng(3)
    idxs = np.sort(rng.integers(5_000, len(mid) - 1, size=16))
    tp, eps = FIXED_BL

    def sig(i, ts_, p, bv, sv):
        return position_signal_at(i, ts_, p, bv, sv, theta_pivot_bps=tp, break_eps_bps=eps)

    def sig_ad(i, ts_, p, bv, sv):
        sub = np.asarray(p[: int(i) + 1], float)
        legs = run_bigline_adaptive(sub, FIXED_AD[0], int(FIXED_AD[1] * 3600))
        if not legs:
            return 0
        return int(legs[-1].side) if legs[-1].forced else 0

    def sig_ad_dip(i, ts_, p, bv, sv):
        j = int(i) + 1
        sub = np.asarray(p[:j], float)
        lb = lean_series(np.asarray(bv[:j], float), np.asarray(sv[:j], float), LEAN_W_1S)
        legs = run_bigline_adaptive(sub, FIXED_AD[0], int(FIXED_AD[1] * 3600),
                                    lean=lb, x_frac=X_FRAC, require_flip=True)
        if not legs:
            return 0
        return int(legs[-1].side) if legs[-1].forced else 0

    ok, fails = assert_no_leakage(sig, ts, mid, dummy, dummy, idxs, reps=2)
    print(f"# LEAKAGE GATE (bigline tp{tp:.0f}/eps{eps:.0f}, sol prefix n={len(mid)}, "
          f"{len(idxs)} idxs): {'PASS' if ok else 'FAIL'} ({len(fails)} fails)")
    ok2, fails2 = assert_no_leakage(sig_ad, ts, mid, dummy, dummy, idxs, reps=2)
    print(f"# LEAKAGE GATE (adaptive f{FIXED_AD[0]:.2f}/w{FIXED_AD[1]:.0f}h): "
          f"{'PASS' if ok2 else 'FAIL'} ({len(fails2)} fails)")
    ok3, fails3 = assert_no_leakage(sig_ad_dip, ts, mid, buy1, sell1, idxs, reps=2)
    print(f"# LEAKAGE GATE (adaptive DIPOLE-confirm x{X_FRAC}): "
          f"{'PASS' if ok3 else 'FAIL'} ({len(fails3)} fails)")
    return ok and ok2 and ok3


def main():
    if "--leakage" in sys.argv:
        leakage_gate()
        return
    if not leakage_gate():
        print("!! leakage FAIL — not running the probe")
        return
    results = []
    for (cell, path, K, tk) in CELLS:
        r = run_cell(cell, path, K, tk)
        if r is None:
            continue
        results.append(r)
        print(f"\n== {cell} ({r['hrs']:.1f}h, gaps {r['gap_hrs']:.1f}h, "
              f"spread {r['spread_bps']:.2f}bps) ==")
        print("  ORACLE   theta  swings/day  med_swing   $/day rt_taker   $/day rt_mk-1")
        for th, o in r["oracle"].items():
            if not o.get("net_day"):
                continue
            print(f"           {th:>5}  {o['swings_day']:>9.1f}  {o['med_swing']:>8.1f}bp"
                  f"  {o['net_day']['rt_taker']:>+13.2f}  {o['net_day']['rt_mk-1']:>+13.2f}")
        print("  ZIGZAG   theta  n_legs  gross/leg  net/leg(tk)   $/hr(tk)   rev$/hr   shuf$/hr")
        for th, z in r["zigzag"].items():
            if not z.get("rows"):
                continue
            rw = z["rows"]["rt_taker"]
            print(f"           {th:>5}  {z['n_legs']:>6}  {z['gross_leg']:>+8.1f}  {rw['net_leg']:>+10.1f}"
                  f"  {rw['dhr']:>+9.2f}  {rw['dhr_rev']:>+8.2f}  {z['shuffle_dhr']:>+8.2f}")
        print("  BIGLINE  cfg          n  gross/leg  net/leg(tk)  $/hr(tk)  rev$/hr  shuf$/hr"
              "  expo  medhold  forced")
        for cfg, b in r["bigline"].items():
            if not b.get("rows"):
                print(f"           {cfg:<12} {b['n_legs']:>2}  (no legs)")
                continue
            rw = b["rows"]["rt_taker"]
            shuf = b.get("shuffle_dhr")
            print(f"           {cfg:<12} {b['n_legs']:>2}  {b['gross_leg']:>+8.1f}  {rw['net_leg']:>+10.1f}"
                  f"  {rw['dhr']:>+8.2f}  {rw['dhr_rev']:>+7.2f}  "
                  f"{'    n/a ' if shuf is None else f'{shuf:>+8.2f}'}"
                  f"  {b['exposure']:>4.0%}  {b['med_hold_h']:>6.2f}h  {b['n_forced']}")
        print("  ADAPTIVE cfg          n  gross/leg  net/leg(tk)  $/hr(tk)  rev$/hr  shuf$/hr"
              "  expo  medhold  forced")
        for cfg, b in r.get("adaptive", {}).items():
            if not b.get("rows"):
                print(f"           {cfg:<12} {b['n_legs']:>2}  (no legs)")
                continue
            rw = b["rows"]["rt_taker"]
            print(f"           {cfg:<12} {b['n_legs']:>2}  {b['gross_leg']:>+8.1f}  {rw['net_leg']:>+10.1f}"
                  f"  {rw['dhr']:>+8.2f}  {rw['dhr_rev']:>+7.2f}  {b['shuffle_dhr']:>+8.2f}"
                  f"  {b['exposure']:>4.0%}  {b['med_hold_h']:>6.2f}h  {b['n_forced']}")
        print("  SPLITS (tp60/eps10 / adaptive f0.25w4h / +dipole / zz100), $/hr rt_taker:")
        for w, s in r["splits"].items():
            def _g(key):
                d = s.get(key, {})
                v = d.get("rows", {}).get("rt_taker", {}).get("dhr")
                return (v if v is None else f"{v:+.2f}"), d.get("n_legs", 0)
            bl, nb = _g("bigline")
            ad, na = _g("adaptive")
            dp, nd = _g("dipole")
            zz, nz = _g("zigzag")
            print(f"           {w}: bigline {bl} (n={nb})   adaptive {ad} (n={na})   "
                  f"dipole {dp} (n={nd})   zigzag {zz} (n={nz})")

    out = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "_s54_bigline_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=1)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
