"""_info_dipole_gated_swing.py — the UNIFIED gated swing challenger (S36b NEXT #2).

Not a bake-off (`tools-are-complementary-not-competing`). This composes the pieces by what each
is GOOD AT, per cell:
  - TIMING   : the 1-sec price-reversal trigger (`candidates`) — fires AT the turn (~5-6 bps off).
  - FILTER   : the OD dipole `divergence()` (exhaustion/divergence) — decides WHICH turns are real
               (the 64% read; the harness shows it beats raw OFI on precision + bps-to-turn).
  - STAND-ASIDE: the regime master-gate (ER / C) — suppresses calls in straight runs / toxic flow,
               PER CELL, only where it earns its place (rescues bleeders, left off where the dipole
               already wins).
  - COST     : scored at the per-leg MAKER floor (the decisive economic lever).

Discipline (load-bearing):
  1. MANDATORY pre-entry leakage gate (`assert_no_leakage`) on the dipole filter BEFORE scoring.
  2. Out-of-sample (tune IS 60%, score OOS 40%), true turns = ZigZag 20 bps swings.
  3. PER-CELL deploy decision: pick the best config {un-gated | ER-gated | C-gated} that clears net>0
     at the maker floor WITH real trades (guards against the degenerate "trade less = lose less"
     no-trade wall on a single window).
  4. Runs on whatever realbins/ holds. With the free-historical backfill (Bybit/Binance dumps +
     Coinbase/Kraken REST) materialized, this is now the MULTI-COIN / MULTI-REGIME re-run (S36b
     NEXT #1) — the data span per cell is recorded in the result JSON config. The KILL gate is
     honest: deploy ONLY cells that clear net>0 at the maker floor across the span; stand aside
     elsewhere. Do NOT size real capital off a cell that only clears thin/marginal.

Run: python _info_dipole_gated_swing.py
"""
from __future__ import annotations

import json

import numpy as np

from odcore.info_dipole import divergence
from odcore.leakage import assert_no_leakage
from _info_dipole_swing_backtest import load_series
from _info_dipole_harness import IS_FRAC
from _info_dipole_regime_gate import evaluate

# per-cell deploy guard: the degenerate failure on one window is NO trades, NOT low recall —
# the regime gate EARNS its place by trading less (lower recall, positive net), so we must not
# reject low recall. Require only net>0 at maker AND enough real trades to not be noise.
MIN_CALLS = 10             # must actually trade (guards the degenerate no-trade wall)
THIN_RECALL = 0.15         # below this, deploy is flagged THIN (low coverage -> confirm, don't size up)
DIP_W = 900               # dipole filter window for the leakage probe (matches regime_gate sane default)

# the configs we choose among, by what each is good at (champion kept as the classical reference)
STACK_CONFIGS = ["CHALLENGER", "CHALL+ERgate", "CHALL+Cgate"]
LABEL = {"CHALLENGER": "dipole (un-gated)", "CHALL+ERgate": "dipole + ER stand-aside",
         "CHALL+Cgate": "dipole + C stand-aside"}


def make_signal_at(W):
    """The stacked detector's FILTER value as-of i: reversal conviction over the strictly-prior
    window (0.0 if the dipole doesn't expect a reversal, None if too few points). Leakage-checkable."""
    def signal_at(i, ts, p, bv, sv):
        lo = int(np.searchsorted(ts, ts[i] - W))
        if i - lo < 6:
            return None
        drift = float(p[i] - p[lo])
        dv = divergence(bv[lo:i + 1], sv[lo:i + 1], drift)
        if dv is None:
            return None
        return float(dv["reversal_conviction"]) if dv["expect"] == "reversal" else 0.0
    return signal_at


def leakage_gate(series) -> bool:
    """MANDATORY: the dipole filter computed at i must not change when data after i is corrupted."""
    sig = make_signal_at(DIP_W)
    all_clean = True
    for s in sorted(series):
        ts, p, bv, sv = series[s]
        if len(p) < 100:
            continue
        idxs = np.linspace(int(len(p) * 0.2), len(p) - 2, 30, dtype=int)
        passed, fails = assert_no_leakage(sig, ts, p, bv, sv, idxs, reps=2, seed=0)
        flag = "PASS" if passed else f"FAIL ({len(fails)} leaks)"
        print(f"  leakage {s:18s}: {flag}")
        all_clean = all_clean and passed
    return all_clean


def pick_deploy(cell_res: dict) -> tuple[str, str]:
    """Per-cell: choose the config that clears net>0 at maker with enough real trades; else stand
    aside. The regime-gated configs are legitimately low-recall — that's the gate earning its place,
    not a degenerate. Returns (config_key_or_None, verdict_text)."""
    eligible = []
    for k in STACK_CONFIGS:
        d = cell_res.get(k)
        if d is None:
            continue
        if d["net_maker"] > 0 and (d.get("n_calls") or 0) >= MIN_CALLS:
            eligible.append((d["net_maker"], k))
    if not eligible:
        # nothing clears — is it because it bleeds, or because every config goes near-flat?
        best_net = max((cell_res[k]["net_maker"] for k in STACK_CONFIGS if cell_res.get(k)), default=0)
        return None, f"stand aside (best net@maker {best_net:+.0f}, no positive config with real trades)"
    eligible.sort(reverse=True)
    best = eligible[0][1]
    d = cell_res[best]
    thin = " [THIN — low coverage, confirm before sizing]" if (d.get("recall") or 0) < THIN_RECALL else ""
    return best, f"deploy {LABEL[best]} (net@maker {d['net_maker']:+.0f}, recall {d.get('recall')}){thin}"


def main():
    series = load_series("realbins")
    print("UNIFIED GATED SWING CHALLENGER (S36b NEXT #2) — per-cell stack, maker floor, OOS.\n"
          "Stack: 1-sec price-reversal = TIMING; dipole divergence = FILTER; regime gate = STAND-ASIDE.\n")

    print("STEP 0 — MANDATORY pre-entry leakage gate on the dipole filter:")
    if not leakage_gate(series):
        print("\nABORT: dipole filter leaks — do NOT score a leaking signal.")
        return
    print("  -> leak-free. Proceeding to score.\n")

    print(f"OOS (tune first {int(IS_FRAC*100)}%, score last {int((1-IS_FRAC)*100)}%); "
          f"true turns = 20bps ZigZag; net @ MAKER floor.\n")
    print(f"{'cell':16s} {'config':22s} {'calls':>5s} {'recall':>6s} {'prec':>5s} "
          f"{'bps2turn':>8s} {'net@mk':>7s}   DEPLOY")
    print("-" * 100)

    deploy_map = {}
    out = {}
    spans = {}
    for s in sorted(series):
        ts, p, bv, sv = series[s]
        if len(ts):
            spans[s] = {"n": int(len(ts)), "span_days": round(float(ts[-1] - ts[0]) / 86400, 2)}
        cut = int(len(p) * IS_FRAC)
        seg_is = (ts[:cut], p[:cut], bv[:cut], sv[:cut])
        seg_oos = (ts[cut:], p[cut:], bv[cut:], sv[cut:])
        r = evaluate(seg_is, seg_oos)
        out[s] = r
        chosen, verdict = pick_deploy(r)
        deploy_map[s] = {"config": chosen, "verdict": verdict}
        # show the chosen config row (or un-gated if standing aside), plus the champion reference
        showk = chosen or "CHALLENGER"
        d = r[showk]
        print(f"{s:16s} {LABEL.get(showk, showk):22s} {d['n_calls']:>5d} {d['recall']:>6.3f} "
              f"{str(d['precision']):>5s} {str(d['bps_to_turn']):>8s} {d['net_maker']:>+7.0f}   {verdict}")
    print("-" * 100)

    print("\nPER-CELL DEPLOY MAP (on the materialized realbins span; deploy ONLY net>0 cells, stand aside else):")
    for s in sorted(deploy_map):
        print(f"  {s:16s} -> {deploy_map[s]['verdict']}")
    n_deploy = sum(1 for v in deploy_map.values() if v["config"])
    print(f"\n  {n_deploy}/{len(deploy_map)} cells clear net>0 at the maker floor with real trades on this window.")
    print("  (Per-cell rule: keep the stack where it earns its place; stand aside elsewhere.)")

    with open("_info_dipole_gated_swing_results.json", "w") as f:
        json.dump({"config": {"min_calls": MIN_CALLS, "thin_recall": THIN_RECALL,
                              "is_frac": IS_FRAC,
                              "data": "realbins/ (free-historical backfill: Bybit/Binance dumps + "
                                      "Coinbase/Kraken REST); multi-coin / multi-regime",
                              "cell_spans": spans},
                   "deploy_map": deploy_map, "per_cell": out}, f, indent=2)
    print("\nWrote _info_dipole_gated_swing_results.json")


if __name__ == "__main__":
    main()
