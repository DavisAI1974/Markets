"""_s57_freight_veto.py — S57 JOB 3: the FREIGHT-TRAIN VETO as a sandbox variant, NO-GATES scored.

S56 worst-10 anatomy (both cells, ARM0): every tail loser was a counter-entry into a violent
spike/flush — 36s-2min legs, -89..-132bp — and on 10/10 the R1 dipole descriptor at the pivot
already said `continue` with reversal_conviction 0.00. Candidate veto: skip the flip (stay FLAT
for that leg — S56 rule: risk control flats, never trades a fallback) when
    dipole_class == "continue" AND rev_conv <= RC_EPS AND trailing velocity >= threshold.

Scoring (Greg's standing NO-GATES law, S53): judge on net $/hr AND legs/hr vs the un-vetoed
cell — eliminating losers eliminates winners too, so the verdict is the TOTAL, not per-leg
quality. Controls: random-matched veto (same n, targeting shuffled away; 20 seeds) and
reversed-targeting veto (same n from the calm end of the velocity ranking). Velocity threshold
is SWEPT (S56 lesson: the ARM40 knife-edge — never promote a grid point without its curve).

Inputs: paper_ledger_sandbox.jsonl (per-leg rows incl. causal descriptors, deduped) +
/tmp/<coin>_bybit_book.jsonl.gz (mid series for the trailing-velocity feature). All causal:
velocity is a trailing window ending at the entry cell.

Usage: python scripts/_s57_freight_veto.py [--vel-w 300] [--rc-eps 0.05] [--rep 5000]
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _birth_probe import load_book                    # noqa: E402
from _liquidity_dive import build_channels            # noqa: E402
from odcore.platform import FLOW_W                    # noqa: E402

LEDGER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "paper_ledger_sandbox.jsonl")
QUANTS = (80.0, 90.0, 95.0, 97.5, 99.0)               # velocity-threshold response curve


def dollars_per_hr(net_bps, hrs, rep):
    return float(np.sum(net_bps)) / 1e4 * rep / hrs


def cell_report(coin, rows, args):
    path = f"/tmp/{coin}_bybit_book.jsonl.gz"
    if not os.path.exists(path):
        print(f"[{coin}_bybit] no book"); return
    raw = load_book(path)
    ts0 = float(raw["ts"][0])
    # the REGULAR 0.1s grid the platform trades on — ledger ts = ts0 + grid_idx*0.1 (run_cell),
    # so the inversion below is exact on THIS mid, not on the gap-carrying raw rows
    _, g = build_channels(path, 1, FLOW_W, raw=raw)
    mid = np.asarray(g["mid"], float)
    hrs = (float(raw["ts"][-1]) - ts0) / 3600.0

    net = np.asarray([r["net_bps"] for r in rows])
    # entry grid index from the ledger ts (grid = 0.1s cells, ts = t0 + idx*0.1)
    idx = np.asarray([int(round((r["ts"] - ts0) / 0.1)) for r in rows])
    ok = (idx >= 0) & (idx < len(mid))
    if not np.all(ok):
        print(f"  ! {np.sum(~ok)} legs outside book grid dropped")
        rows = [r for r, k in zip(rows, ok) if k]; net, idx = net[ok], idx[ok]
    # trailing velocity into the entry (causal): |mid move| over the last vel_w cells
    lo = np.maximum(0, idx - args.vel_w)
    vel = np.abs(mid[idx] - mid[lo]) / np.where(mid[lo] > 0, mid[lo], 1.0) * 1e4
    # the S56 tail flag at the pivot
    flag = np.asarray([(r["dipole_class"] == "continue")
                       and (r["rev_conv"] is not None and r["rev_conv"] <= args.rc_eps)
                       for r in rows])

    base_hr = dollars_per_hr(net, hrs, args.rep)
    n = len(net)
    print(f"\n[{coin}_bybit] {n} legs / {hrs:.2f}h  base ${base_hr:+.2f}/hr "
          f"{n / hrs:.0f} legs/hr  win {100 * np.mean(net > 0):.0f}%  "
          f"(continue&rc<={args.rc_eps}: {np.sum(flag)} legs = {100 * np.mean(flag):.0f}%)")
    print(f"  {'thr':>8} {'nveto':>6} | {'VETO $/hr':>10} {'legs/hr':>8} | "
          f"{'random $/hr (20s)':>18} | {'reversed $/hr':>13} | verdict")

    rng = np.random.default_rng(57)
    order_calm = np.argsort(vel)                      # reversed targeting: calmest legs first
    for q in QUANTS:
        thr = float(np.percentile(vel, q))
        veto = flag & (vel >= thr)
        nv = int(np.sum(veto))
        if nv == 0:
            print(f"  P{q:<5} {thr:8.1f} {0:>6} | (no legs vetoed)"); continue
        keep = ~veto
        v_hr = dollars_per_hr(net[keep], hrs, args.rep)
        # random-matched control: same count, targeting shuffled away
        r_hrs = []
        for _ in range(20):
            ridx = rng.choice(n, size=nv, replace=False)
            m = np.ones(n, bool); m[ridx] = False
            r_hrs.append(dollars_per_hr(net[m], hrs, args.rep))
        # reversed targeting: veto the nv CALMEST legs instead
        m = np.ones(n, bool); m[order_calm[:nv]] = False
        rev_hr = dollars_per_hr(net[m], hrs, args.rep)
        verdict = "PASS" if (v_hr > base_hr and v_hr > np.mean(r_hrs) + 2 * np.std(r_hrs)
                             and v_hr > rev_hr) else "no"
        print(f"  P{q:<5} {thr:8.1f} {nv:>6} | {v_hr:>+10.2f} {np.sum(keep) / hrs:>8.0f} | "
              f"{np.mean(r_hrs):>+8.2f} ±{np.std(r_hrs):>5.2f} | {rev_hr:>+13.2f} | {verdict}")

    # the loop rule: what the flag actually touches — vetoed column P&L + the tails
    thr95 = float(np.percentile(vel, 95.0))
    veto95 = flag & (vel >= thr95)
    if np.sum(veto95):
        vn = net[veto95]
        print(f"  @P95: vetoed column sums {np.sum(vn):+.1f}bp over {len(vn)} legs "
              f"(winners {np.sum(vn[vn > 0]):+.1f} / losers {np.sum(vn[vn < 0]):+.1f})")
    return dict(coin=coin, rows=rows, net=net, vel=vel, flag=flag, hrs=hrs)


def print_tails(d, args, k=10):
    """Greg's standing loop rule: 10 worst losers + 10 smallest winners, with the veto verdict
    per leg (@P95) so the read shows what the flag would and wouldn't have caught."""
    net, vel, flag, rows = d["net"], d["vel"], d["flag"], d["rows"]
    thr = float(np.percentile(vel, 95.0))
    vetoed = flag & (vel >= thr)
    print(f"\n[{d['coin']}_bybit] WORST {k} (veto@P95 flag per leg):")
    print(f"  {'net_bp':>8} {'swing':>7} {'side':>5} {'class':>10} {'rc':>5} "
          f"{'vel_bp':>7} {'vetoed':>7}")
    for i in np.argsort(net)[:k]:
        r = rows[i]
        rc = f"{r['rev_conv']:.2f}" if r["rev_conv"] is not None else "n/a"
        print(f"  {net[i]:>+8.1f} {r['swing_bps']:>7.1f} {r['side']:>+5d} "
              f"{r['dipole_class']:>10} {rc:>5} {vel[i]:>7.1f} "
              f"{'VETO' if vetoed[i] else '.':>7}")
    win_idx = np.where(net > 0)[0]
    print(f"[{d['coin']}_bybit] SMALLEST {k} winners:")
    for i in win_idx[np.argsort(net[win_idx])[:k]]:
        r = rows[i]
        rc = f"{r['rev_conv']:.2f}" if r["rev_conv"] is not None else "n/a"
        print(f"  {net[i]:>+8.1f} {r['swing_bps']:>7.1f} {r['side']:>+5d} "
              f"{r['dipole_class']:>10} {rc:>5} {vel[i]:>7.1f} "
              f"{'VETO' if vetoed[i] else '.':>7}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vel-w", type=int, default=300, help="trailing velocity window (0.1s cells)")
    ap.add_argument("--rc-eps", type=float, default=0.05, help="reversal-conviction ceiling")
    ap.add_argument("--rep", type=float, default=5000.0, help="flat $ per leg")
    args = ap.parse_args()

    with open(LEDGER) as f:
        rows = [json.loads(x) for x in f if x.strip()]
    print(f"# freight-train veto probe — {len(rows)} sandbox legs, vel_w={args.vel_w} "
          f"({args.vel_w / 10:.0f}s), rc_eps={args.rc_eps}, ${args.rep:.0f}/leg flat, TRUE MM3 fees")
    outs = []
    for coin in ("sol", "eth"):
        d = cell_report(coin, [r for r in rows if r["coin"] == coin], args)
        if d:
            outs.append(d)
    for d in outs:
        print_tails(d, args)


if __name__ == "__main__":
    main()
