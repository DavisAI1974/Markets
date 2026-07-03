"""_s59_promotion_canary.py — S59 ENTRY PROMOTION CANARY (the DoD's proof obligations).

Three assertions, all must PASS before the promotion commit is trusted:
  1. FAITHFUL PORT — odcore.entry_coinbase.armed_midband_flips reproduces the S58 round-6
     reference implementation (scripts/_s58_piece1_reruns.py::machine, naive pred) BIT-FOR-BIT
     on every restored Coinbase book tape, at the registry (theta, c) and at the bounce
     variant (BTC candidate mechanics).
  2. LEAKAGE — truncation invariance of the promoted machine on every tape (causality gate).
  3. BASELINE BIT-IDENTICAL — the baseline paper path (run_cell over platform.DEPLOYED) yields
     bit-identical rows with and without the new module imported (import-side-effect-free;
     the promotion adds cells, it does not touch the baseline forward record).

Usage: python scripts/_s59_promotion_canary.py
"""
import json
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from odcore.entry_coinbase import (COINBASE_MIDBAND, armed_midband_flips,          # noqa: E402
                                   assert_truncation_invariance)
from _s58_piece1_reruns import machine, make_pred, Reads2                          # noqa: E402
from _birth_probe import load_book                                                 # noqa: E402
from _liquidity_dive import build_channels                                         # noqa: E402
from odcore.platform import FLOW_W                                                 # noqa: E402

THETAS = (80.0, 100.0)
C = 0.5


def tapes():
    for coin in ("sol", "btc", "doge", "xrp", "eth"):
        p = f"/tmp/{coin}_coinbase_book.jsonl.gz"
        if not os.path.exists(p):
            print(f"[{coin}] book missing — skipped")
            continue
        raw = load_book(p)
        _, g = build_channels(p, 10 if coin == "btc" else 1, FLOW_W, raw=raw)
        yield coin, (np.asarray(g["mid"], float), np.asarray(g["buy"], float),
                     np.asarray(g["sell"], float))


def main():
    fails = 0

    # 1 + 2: faithful port + leakage, every tape x theta (+ bounce variant)
    for coin, (mid, buy, sell) in tapes():
        sr = Reads2(mid, buy, sell)
        for theta in THETAS:
            ref = machine(mid, sr, theta, C * theta, make_pred("k0"))
            new = armed_midband_flips(mid, theta, C)
            same = (ref == new)
            refb = machine(mid, sr, theta, C * theta, make_pred("k0"), ffb_bp=0.25 * theta)
            newb = armed_midband_flips(mid, theta, C, bounce_frac=0.25)
            sameb = (refb == newb)
            try:
                assert_truncation_invariance(mid, theta, C)
                leak = "PASS"
            except AssertionError:
                leak = "FAIL"
            ok = same and sameb and leak == "PASS"
            fails += 0 if ok else 1
            print(f"[{coin}] th{theta:.0f}: port {'PASS' if same else 'FAIL'} "
                  f"({len(ref)} flips) | bounce {'PASS' if sameb else 'FAIL'} "
                  f"({len(refb)}) | leakage {leak}")

    # 3: baseline bit-identity — run_cell(DEPLOYED) rows identical with/without the new module.
    # Fresh subprocesses so import order is the only difference.
    prog = (
        "import sys,json;sys.path.insert(0,{root!r});sys.path.insert(0,{scr!r});{extra}"
        "from odcore.platform import DEPLOYED, run_cell;"
        "rows=[];[rows.extend(run_cell(c)) for c in DEPLOYED];"
        "print(json.dumps(rows, sort_keys=True))"
    )
    scr = os.path.join(ROOT, "scripts")
    outs = []
    for extra in ("", "import odcore.entry_coinbase;"):
        r = subprocess.run([sys.executable, "-c",
                            prog.format(root=ROOT, scr=scr, extra=extra)],
                           capture_output=True, text=True, cwd=ROOT)
        if r.returncode != 0:
            print("baseline run ERR:", r.stderr[-500:]); fails += 1; outs = None; break
        outs.append(r.stdout.strip().splitlines()[-1])
    if outs:
        same = outs[0] == outs[1]
        n = len(json.loads(outs[0]))
        fails += 0 if same else 1
        print(f"[baseline] run_cell(DEPLOYED) rows with/without module import: "
              f"{'BIT-IDENTICAL' if same else 'DIVERGED'} ({n} rows)")

    # registry sanity print
    print("\nregistry:", ", ".join(f"{c.cell}{'' if c.active else ' (inactive)'}"
                                   for c in COINBASE_MIDBAND))
    print(f"\nCANARY {'PASS' if fails == 0 else f'FAIL ({fails})'}")
    sys.exit(0 if fails == 0 else 1)


if __name__ == "__main__":
    main()
