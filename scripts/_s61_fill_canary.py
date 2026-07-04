"""_s61_fill_canary.py — S61 build (a) canary + honest-fill measurement.

Phase A (pre/post edit): run every Coinbase mid-band registry cell (btc force-active for
measurement) with the DEFAULT fill model and dump the leg rows to JSON — the bit-identical
baseline the wire must reproduce.
Phase B (post edit): same cells with fill_model="queue" — report REAL maker_close%, taker%,
net/leg per fee framing vs the saturated-True baseline.
Usage: python _s61_fill_canary.py A|B|check
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dataclasses import replace
import numpy as np
from odcore.entry_coinbase import COINBASE_MIDBAND, run_midband_cell

SP = os.environ.get("S61_CANARY_DIR", os.path.dirname(os.path.abspath(__file__)))

def run_all(**kw):
    out = {}
    for cfg in COINBASE_MIDBAND:
        c = replace(cfg, active=True)          # btc force-active: measurement, not deploy
        rows = run_midband_cell(c, **kw)
        out[c.cell] = rows
    return out

def summarize(rows):
    if not rows:
        return dict(n=0)
    net = np.array([r["net_bps"] for r in rows])
    mk = np.array([r["maker_close"] for r in rows])
    return dict(n=len(rows), net_per_leg=round(float(net.mean()), 3),
                total_net=round(float(net.sum()), 1),
                maker_close_pct=round(100 * float(mk.mean()), 1),
                win_frac=round(float((net > 0).mean()), 3))

mode = sys.argv[1]
if mode == "A":
    res = run_all()
    json.dump(res, open(f"{SP}/fill_canary_baseline.json", "w"), sort_keys=True)
    for cell, rows in res.items():
        print(cell, summarize(rows))
elif mode == "check":
    res = run_all()
    base = json.load(open(f"{SP}/fill_canary_baseline.json"))
    ok = True
    for cell in base:
        a = json.dumps(base[cell], sort_keys=True)
        b = json.dumps(res.get(cell, []), sort_keys=True)
        stat = "BIT-IDENTICAL" if a == b else "*** DIVERGED ***"
        ok &= (a == b)
        print(cell, stat, summarize(res.get(cell, [])))
    print("CANARY", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
elif mode == "B":
    res = run_all(fill_model="queue")
    base = json.load(open(f"{SP}/fill_canary_baseline.json"))
    json.dump(res, open(f"{SP}/fill_queue_arm.json", "w"), sort_keys=True)
    print(f"{'cell':26s} {'':>4s}  {'front (saturated)':>34s}  |  {'queue (honest)':>34s}")
    for cell, rows in res.items():
        sb, sq = summarize(base.get(cell, [])), summarize(rows)
        print(f"{cell:26s} n={sq.get('n',0):4d}  "
              f"net {sb.get('net_per_leg','-'):>8} mk% {sb.get('maker_close_pct','-'):>6}  |  "
              f"net {sq.get('net_per_leg','-'):>8} mk% {sq.get('maker_close_pct','-'):>6}")
