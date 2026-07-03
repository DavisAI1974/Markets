"""_s57_veto_diagnose.py — WHY did the freight-train veto fail? (Greg: before saying no,
check whether the failure is on OUR end.)

Two candidate tool errors in the S57 first pass (_s57_freight_veto.py):
  (1) UNSIGNED velocity — |mid move| flags trains we are RIDING (winners) exactly like trains
      we are FADING (the S56 loser anatomy = counter-entries). Fix: signed fade-velocity
      fv = -side * (mid[ci] - mid[ci-w]) / mid[ci-w] * 1e4  (>0 = entering AGAINST the move).
  (2) WINDOW — 30s fixed; the S56 violence was read off chart spans of ~36s-2min legs plus
      context. Sweep w = 5s/10s/30s/60s/120s.
Also on the table: population mismatch (S56 anatomy = 30d x 5-coin BINS tail; first pass ran
on the mild 19.5h books tail) — that half is tested separately on the re-pulled bins.

This script, on the books sandbox legs: per window, corr(fade_vel, net), the fade-vs-join
split of the flagged set, worst-10 catch rate, and the NO-GATES $/hr table for the SIGNED
fade-only veto (with random-matched + reversed controls).
"""
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
WINDOWS = (50, 100, 300, 600, 1200)                   # 0.1s cells: 5s/10s/30s/60s/120s
RC_EPS = 0.05
REP = 5000.0


def dollars(net, hrs):
    return float(np.sum(net)) / 1e4 * REP / hrs


def main():
    with open(LEDGER) as f:
        rows = [json.loads(x) for x in f if x.strip()]
    for coin in ("sol", "eth"):
        rs = [r for r in rows if r["coin"] == coin]
        path = f"/tmp/{coin}_bybit_book.jsonl.gz"
        raw = load_book(path)
        ts0 = float(raw["ts"][0])
        _, g = build_channels(path, 1, FLOW_W, raw=raw)
        mid = np.asarray(g["mid"], float)
        hrs = (float(raw["ts"][-1]) - ts0) / 3600.0
        net = np.asarray([r["net_bps"] for r in rs])
        side = np.asarray([r["side"] for r in rs])
        idx = np.asarray([int(round((r["ts"] - ts0) / 0.1)) for r in rs])
        flag = np.asarray([(r["dipole_class"] == "continue")
                           and (r["rev_conv"] is not None and r["rev_conv"] <= RC_EPS)
                           for r in rs])
        n = len(net)
        base = dollars(net, hrs)
        worst = np.argsort(net)[:10]
        print(f"\n[{coin}_bybit] {n} legs base ${base:+.2f}/hr — SIGNED fade-velocity dive")
        print(f"  {'w':>5} | {'corr(fv,net)':>12} | {'fade-share of flag':>18} | "
              f"{'flagged fade $col':>17} {'join $col':>10} | {'worst10 fv>P95':>14}")
        fvs = {}
        for w in WINDOWS:
            lo = np.maximum(0, idx - w)
            mv = (mid[idx] - mid[lo]) / np.where(mid[lo] > 0, mid[lo], 1.0) * 1e4
            fv = -side * mv                            # >0 = counter-entry (fading the move)
            fvs[w] = fv
            corr = float(np.corrcoef(fv, net)[0, 1])
            thr = float(np.percentile(fv, 95.0))
            fade_flag = flag & (fv >= thr)             # flagged + strongly fading
            join_flag = flag & (fv <= -thr)            # flagged + strongly riding
            fcol = float(np.sum(net[fade_flag])) if np.any(fade_flag) else 0.0
            jcol = float(np.sum(net[join_flag])) if np.any(join_flag) else 0.0
            w10 = int(np.sum(fvs[w][worst] >= thr))
            print(f"  {w / 10:>4.0f}s | {corr:>+12.3f} | "
                  f"{np.sum(fade_flag):>7} vs join {np.sum(join_flag):>4} | "
                  f"{fcol:>+17.1f} {jcol:>+10.1f} | {w10:>10}/10")
        # NO-GATES table for the best-motivated variant: SIGNED fade-only veto, w sweep @P95
        print(f"  SIGNED fade-only veto (continue&rc<={RC_EPS} & fv>=P95) — NO-GATES:")
        rng = np.random.default_rng(57)
        for w in WINDOWS:
            fv = fvs[w]
            thr = float(np.percentile(fv, 95.0))
            veto = flag & (fv >= thr)
            nv = int(np.sum(veto))
            if nv == 0:
                print(f"    w={w/10:>3.0f}s: no legs vetoed"); continue
            v = dollars(net[~veto], hrs)
            r_hrs = []
            for _ in range(20):
                m = np.ones(n, bool)
                m[rng.choice(n, size=nv, replace=False)] = False
                r_hrs.append(dollars(net[m], hrs))
            m = np.ones(n, bool); m[np.argsort(fv)[:nv]] = False   # reversed: most-joining legs
            rev = dollars(net[m], hrs)
            tag = "PASS" if (v > base and v > np.mean(r_hrs) + 2 * np.std(r_hrs) and v > rev) \
                else "no"
            print(f"    w={w/10:>3.0f}s thr={thr:>+6.1f}bp nveto={nv:>4}: "
                  f"${v:+.2f}/hr vs base ${base:+.2f} | rnd ${np.mean(r_hrs):+.2f}±{np.std(r_hrs):.2f} "
                  f"| rev ${rev:+.2f} | {tag}")
        # the tail's pre-entry signature, signed, all windows — is the tail visible at ALL?
        print(f"  worst-10 signed fade-velocity by window (bp; + = we faded the move):")
        hdr = "    net_bp  " + "".join(f"{f'{w/10:.0f}s':>8}" for w in WINDOWS)
        print(hdr)
        for i in worst:
            print(f"    {net[i]:>+6.1f}  " + "".join(f"{fvs[w][i]:>8.1f}" for w in WINDOWS))


if __name__ == "__main__":
    main()
