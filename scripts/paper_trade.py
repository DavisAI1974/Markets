"""paper_trade.py — forward paper-trading harness over odcore.platform (THE ONE VERSION, S55).

This file is now a THIN HARNESS: every decision (flips, executor, sizing, dipole descriptors,
gates, fill model) lives in `odcore/platform.py`, which is the single decision layer shared by
paper, research, and (when a venue is secured) live. Nothing here decides anything — it parses
flags, picks the per-cell configs from platform.DEPLOYED, appends the deduped forward ledger,
and prints the shakeout. History: the decision logic that used to live inline here was promoted
to the platform module in S55 (Greg: "compile 1 version"; the sized-trades drift was the tell).

CAUSAL by construction (see platform docstring). Appends to the persistent JSONL ledger, deduped
by (cell, entry_ts); over time the ledger IS the multi-window out-of-sample test. Variant runs
(--dipole-entry / --dipole-exit) route to the SANDBOX ledger — the baseline forward record stays
pure. DOES NOT trade real money.
"""
from __future__ import annotations
import sys, os, argparse
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from odcore.platform import (DEPLOYED, LEDGER, SANDBOX_LEDGER, run_cell, load_ledger,
                             append_ledger)

# S48 cover-grace per-cell map lives in platform.DEPLOYED (doge 600, rest 300)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--maker", type=float, default=0.0); ap.add_argument("--taker", type=float, default=5.0)
    ap.add_argument("--alpha", type=float, default=1.0); ap.add_argument("--roll", type=int, default=200)
    ap.add_argument("--grace", type=int, default=-1, help="cover-grace cells; -1 = per-cell map")
    ap.add_argument("--dipole-entry", action="store_true",
                    help="S55: gate flip actionability on the S36 divergence read at the pivot (opt-in)")
    ap.add_argument("--dipole-exit", type=str, default="",
                    help="S55 R8: 'arm_hi,exit_lo' lean-collapse exit, e.g. '0.10,0.0' (opt-in)")
    a = ap.parse_args()
    dx = tuple(float(x) for x in a.dipole_exit.split(",")) if a.dipole_exit else None
    ledger_path = LEDGER
    if a.dipole_entry or dx:
        # SANDBOX ledger for variant runs — the standing forward ledger stays pure baseline
        # (S53 rule: sandbox before committing changes; adoption via controls, not flag drift).
        ledger_path = SANDBOX_LEDGER
        print(f"# dipole variant run (entry={a.dipole_entry} exit={dx}) -> SANDBOX ledger "
              f"{os.path.basename(ledger_path)}")
    existing = load_ledger(ledger_path)
    rows = []
    for cfg in DEPLOYED:
        cfg.maker_fee, cfg.taker_fee = a.maker, a.taker
        cfg.alpha, cfg.roll = a.alpha, a.roll
        if a.grace >= 0:
            cfg.grace = a.grace
        cfg.dipole_entry, cfg.dipole_exit = a.dipole_entry, dx
        try:
            rows += run_cell(cfg)
        except Exception as e:
            print(f"# {cfg.coin} ERR {e}")
    new = append_ledger(rows, ledger_path, existing=existing)
    print(f"# paper_trade: +{len(new)} new trades (maker={a.maker} taker={a.taker} alpha={a.alpha})")
    ledger = existing + new
    print(f"# LEDGER TOTAL {len(ledger)} trades across all runs. per-cell shakeout (net-of-fee):")
    print(f"# {'cell':16s}{'n':>6}{'flat_net':>10}{'sized_net':>11}{'win%':>6}{'taker%':>8}{'mean_sz':>9}")
    for cfg in DEPLOYED:
        rs = [r for r in ledger if r["coin"] == cfg.coin]
        if not rs:
            print(f"# {cfg.cell:16s}{0:>6}"); continue
        fn = sum(r["net_bps"] for r in rs); sn = sum(r["sized_net"] for r in rs)
        win = 100 * np.mean([r["net_bps"] > 0 for r in rs]); tk = 100 * np.mean([not r["maker_close"] for r in rs])
        msz = float(np.mean([r["size_mult"] for r in rs]))
        print(f"# {cfg.cell:16s}{len(rs):>6}{fn:>+10.1f}{sn:>+11.1f}{win:>6.0f}{tk:>8.0f}{msz:>9.2f}")


if __name__ == "__main__":
    main()
