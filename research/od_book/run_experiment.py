"""
run_experiment.py — OD-BOOK orchestration (spec §6), with a one-shot T_test guard.

Sequence:
  1. Build x(t) + walk-forward splits (frozen, time-ordered).
  2. Tune CHAMPION (VAR order p + ridge alpha) and CHALLENGER (DMD rank) on VAL.
  3. Metrics + KILL gate are frozen (KILL_GATE.md).
  4. Single T_test pass — locked behind --commit-ttest AND a sentinel file so it
     can be touched EXACTLY ONCE. No quiet re-runs, no metric-swapping.
  5. Apply the 3-part KILL gate; write a result JSON for MASTER_DISCOVERIES.

Default (no --commit-ttest) runs VAL-only: tunes + reports on train/val, never
touches test. Use that freely while data accrues. Run the real thing once, on the
multi-day data/btc-book dataset, with --commit-ttest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import book_state          # noqa: E402
import champion            # noqa: E402
import challenger_od       # noqa: E402
import metrics             # noqa: E402
import splits              # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SENTINEL = os.path.join(HERE, ".ttest_committed.json")

HORIZONS = [1, 5, 10]          # 100ms, 500ms, 1s on the 100ms grid
FEE_BPS = 22.0
THETA_BPS = 22.0
DEADBAND_GRID = (0.0, 1.0, 2.0, 5.0, 10.0, 20.0)   # min predicted move to take a side
# KILL-gate margins (frozen)
SKILL_MARGIN = 0.0             # challenger must EXCEED champion mid_price R²
WANDER_MAX = 0.15              # max acceptable top-k spectral drift (rel. units)


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
    except Exception:
        return "unknown"


def _data_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


# ----------------------------------------------------------------------------- #
# tuning (VAL only)
# ----------------------------------------------------------------------------- #
def tune_champion(Xtr, Xva, mid_tr, mid_va, cols):
    mid_ret_idx = cols.index("mid_ret")
    best, best_key = None, None
    for p in (1, 2, 3):
        for alpha in (0.0, 1.0, 10.0, 100.0):
            m = champion.fit_var(Xtr, p=p, alpha=alpha)
            r = metrics.mid_path_skill(m, Xva, mid_va, 1, mid_ret_idx)
            if np.isfinite(r) and (best is None or r > best_key):
                best, best_key, best_cfg = m, r, (p, alpha)
    return best, {"p": best_cfg[0], "alpha": best_cfg[1], "val_mid_r2": best_key}


def tune_challenger(Xtr, Xva, mid_tr, mid_va, cols):
    mid_ret_idx = cols.index("mid_ret")
    D = Xtr.shape[1]
    best, best_key, best_cfg = None, None, None
    for energy in (0.95, 0.99, 0.999, 0.9999):
        m = challenger_od.fit_dmd(Xtr, rank=None, h=1, energy=energy)
        r = metrics.mid_path_skill(m, Xva, mid_va, 1, mid_ret_idx)
        if np.isfinite(r) and (best is None or r > best_key):
            best, best_key, best_cfg = m, r, (energy, getattr(m, "rank", D))
    return best, {"energy": best_cfg[0], "rank": best_cfg[1], "val_mid_r2": best_key}


def tune_deadband(model, X, mid, cols, horizon) -> float:
    """Pick the deadband (min predicted move to take a side) that maximizes net
    swing PnL on the given (val) block — cuts fee churn without leaking test."""
    best_db, best_net = 0.0, None
    for db in DEADBAND_GRID:
        tc = metrics.turn_as_consequence(model, X, mid, cols, horizon,
                                         FEE_BPS, THETA_BPS, deadband_bps=db)
        net = tc["pnl_net_bps"]
        if best_net is None or net > best_net:
            best_net, best_db = net, db
    return best_db


def score(model, X, mid, cols, deadbands: dict):
    fs = metrics.forecast_skill(model, X, mid, cols, HORIZONS)
    tc = {h: metrics.turn_as_consequence(model, X, mid, cols, h, FEE_BPS, THETA_BPS,
                                         deadband_bps=deadbands.get(h, 0.0))
          for h in HORIZONS}
    return {"forecast_skill": fs, "turn": tc, "deadbands": deadbands}


def salvage(champ_sc, chal_sc, stab) -> dict:
    """Even on a KILL, record what's REUSABLE — the components the operator
    improves on and whether the operator is stable enough to serve as a
    gate/feature in the larger architecture. One part not clearing the fee floor
    does not mean the whole thing is discarded."""
    comps = ["mid_price", "spread", "tob_imb", "depth_imb", "flow"]
    wins = {}
    for h in HORIZONS:
        for c in comps:
            cc = champ_sc["forecast_skill"][h].get(c, float("nan"))
            dd = chal_sc["forecast_skill"][h].get(c, float("nan"))
            if np.isfinite(dd) and np.isfinite(cc) and dd > cc:
                wins.setdefault(c, []).append(h)
    drift = stab.get("topk_drift_max", float("nan"))
    usable = bool(np.isfinite(drift) and drift <= WANDER_MAX)
    return {
        "challenger_component_wins": wins,
        "operator_stable_enough_as_feature": usable,
        "note": ("Standalone-at-the-fee-floor is one verdict; components the "
                 "operator wins on + a stable operator remain reusable as gates / "
                 "spread-adjusters / features in the architecture (not discarded)."),
    }


def spectrum_walk(X, cols):
    eigs_list = []
    for tr, _ in splits.walk_forward(len(X), n_windows=6, train_frac=0.5):
        try:
            m = challenger_od.fit_dmd(X[tr], rank=None, h=1, energy=0.999)
            eigs_list.append(getattr(m, "eigs"))
        except Exception:
            pass
    return metrics.spectrum_stability(eigs_list)


def kill_gate(champ_sc, chal_sc, stab) -> dict:
    # 1. challenger exceeds champion on mid_price R² at >= 1 horizon
    leg1 = False
    per_h = {}
    for h in HORIZONS:
        c = champ_sc["forecast_skill"][h].get("mid_price", float("nan"))
        d = chal_sc["forecast_skill"][h].get("mid_price", float("nan"))
        per_h[h] = {"champ": c, "chal": d, "chal_wins": bool(d > c + SKILL_MARGIN)}
        if d > c + SKILL_MARGIN:
            leg1 = True
    # 2. translates to a turn/PnL improvement surviving the fee floor
    leg2 = False
    pnl_cmp = {}
    for h in HORIZONS:
        c = champ_sc["turn"][h]["pnl_net_bps"]
        d = chal_sc["turn"][h]["pnl_net_bps"]
        pnl_cmp[h] = {"champ_net_bps": c, "chal_net_bps": d}
        if d > c and d > 0:
            leg2 = True
    # 3. operator does not wander
    drift = stab.get("topk_drift_max", float("nan"))
    leg3 = bool(np.isfinite(drift) and drift <= WANDER_MAX)
    passed = leg1 and leg2 and leg3
    return {
        "leg1_forecast_skill": {"pass": leg1, "per_horizon": per_h},
        "leg2_turn_net_of_fee": {"pass": leg2, "per_horizon": pnl_cmp},
        "leg3_operator_stable": {"pass": leg3, "topk_drift_max": drift,
                                 "threshold": WANDER_MAX},
        "VERDICT": "PASS" if passed else "KILL",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("data", help="book snapshot file (gzipped JSONL)")
    ap.add_argument("--commit-ttest", action="store_true",
                    help="touch T_test (ONCE). Without this, VAL-only.")
    ap.add_argument("--out", default=os.path.join(HERE, "od_book_result.json"))
    args = ap.parse_args()

    bs = book_state.build_state(args.data)
    print(f"[odbook] {bs.n} states, {len(bs.cols)} dims, dropped {bs.n_dropped}, "
          f"span {(bs.ts[-1]-bs.ts[0])/60:.1f} min")
    if bs.n < 1000:
        print("[odbook] too few states; collect more before any T_test.")
        # still allow val-mode plumbing
    sp = splits.three_way(bs.n, 0.6, 0.2)
    Xtr, Xva, Xte = bs.X[sp.train], bs.X[sp.val], bs.X[sp.test]
    mid_tr, mid_va, mid_te = bs.mid[sp.train], bs.mid[sp.val], bs.mid[sp.test]

    champ, champ_cfg = tune_champion(Xtr, Xva, mid_tr, mid_va, bs.cols)
    chal, chal_cfg = tune_challenger(Xtr, Xva, mid_tr, mid_va, bs.cols)
    print(f"[odbook] champion: {champ_cfg}")
    print(f"[odbook] challenger: {chal_cfg}")

    # deadbands tuned on VAL (applied unchanged to TEST in the gated pass)
    champ_db = {h: tune_deadband(champ, Xva, mid_va, bs.cols, h) for h in HORIZONS}
    chal_db = {h: tune_deadband(chal, Xva, mid_va, bs.cols, h) for h in HORIZONS}
    print(f"[odbook] tuned deadbands (bps) champ={champ_db} chal={chal_db}")

    if not args.commit_ttest:
        print("\n[odbook] VAL-ONLY (T_test NOT touched). Scoring on val:")
        champ_sc = score(champ, Xva, mid_va, bs.cols, champ_db)
        chal_sc = score(chal, Xva, mid_va, bs.cols, chal_db)
        _report(champ_sc, chal_sc)
        # operator stability over train+val only (test untouched)
        ntv = len(sp.train) + len(sp.val)
        stab_va = spectrum_walk(bs.X[:ntv], bs.cols)
        print(f"\n[odbook] salvage (reusable parts): "
              f"{json.dumps(salvage(champ_sc, chal_sc, stab_va), indent=2)}")
        print("\n[odbook] Re-run with --commit-ttest on the multi-day dataset for "
              "the single gated decision.")
        return

    # --- T_test: exactly once ---
    if os.path.exists(SENTINEL):
        prev = json.load(open(SENTINEL))
        print(f"\n[odbook] REFUSING: T_test already committed once "
              f"(at {prev['utc']} on data {prev['data_hash']}, sha {prev['git_sha']}).")
        print("[odbook] The gate is frozen. Delete the sentinel only if you "
              "intend to invalidate the pre-registration.")
        sys.exit(2)

    print("\n[odbook] === SINGLE T_TEST PASS (committing) ===")
    champ_sc = score(champ, Xte, mid_te, bs.cols, champ_db)
    chal_sc = score(chal, Xte, mid_te, bs.cols, chal_db)
    stab = spectrum_walk(bs.X, bs.cols)
    gate = kill_gate(champ_sc, chal_sc, stab)
    salv = salvage(champ_sc, chal_sc, stab)
    _report(champ_sc, chal_sc)
    print(f"\n[odbook] spectrum stability: {stab}")
    print(f"[odbook] KILL GATE: {json.dumps(gate, indent=2)}")
    print(f"[odbook] salvage (reusable even on KILL): {json.dumps(salv, indent=2)}")
    print(f"\n[odbook] *** VERDICT: {gate['VERDICT']} ***")

    result = {
        "experiment": "OD-BOOK", "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_sha": _git_sha(), "data": os.path.basename(args.data),
        "data_hash": _data_hash(args.data), "n_states": bs.n, "grid_s": bs.grid_s,
        "champion_cfg": champ_cfg, "challenger_cfg": chal_cfg,
        "champion_score": _jsonable(champ_sc), "challenger_score": _jsonable(chal_sc),
        "spectrum_stability": stab, "kill_gate": gate, "salvage": salv,
    }
    json.dump(result, open(args.out, "w"), indent=2)
    json.dump({"utc": result["utc"], "git_sha": result["git_sha"],
               "data_hash": result["data_hash"], "verdict": gate["VERDICT"]},
              open(SENTINEL, "w"), indent=2)
    print(f"[odbook] wrote {args.out} + sentinel. Log to MASTER_DISCOVERIES.json next.")


def _jsonable(d):
    return json.loads(json.dumps(d, default=lambda x: float(x)
                                 if isinstance(x, (np.floating, np.integer)) else str(x)))


def _report(champ_sc, chal_sc):
    print("\n  mid_price R² (vs persistence-of-price):")
    print("    horizon   champion   challenger")
    for h in HORIZONS:
        c = champ_sc["forecast_skill"][h].get("mid_price", float("nan"))
        d = chal_sc["forecast_skill"][h].get("mid_price", float("nan"))
        print(f"    {h:>5}    {c:>9.4f}   {d:>9.4f}  {'<-chal' if d>c else ''}")
    print("\n  swing PnL net of 22 bps (bps total):")
    print("    horizon   champion   challenger   flips(ch/ca)")
    for h in HORIZONS:
        ct = champ_sc["turn"][h]; dt = chal_sc["turn"][h]
        print(f"    {h:>5}    {ct['pnl_net_bps']:>9.1f}   {dt['pnl_net_bps']:>9.1f}"
              f"   {ct['pnl_n_flips']}/{dt['pnl_n_flips']}")


if __name__ == "__main__":
    main()
