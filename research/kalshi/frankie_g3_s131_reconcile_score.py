#!/usr/bin/env python3
"""Reconcile S131 score against S129 on genuinely common definitions.

The old S129 score labels its target ``actual`` but its per-day values are the session open-to-close
NET, not the full prior-close-to-close day move. S131's current output contract explicitly separates
an overnight gap from the open-to-close P50 path. Comparing S129's session-net MAE with S131's full
day-move MAE is therefore wrong.

This post-score reconciliation proves the old basis row-for-row against the exact NGV25 actual built
by S131, then reports:
- S131 full-day endpoint score (new metric; includes forecast/actual gaps),
- S131 session-net endpoint score (apples-to-apples with S129's reported endpoint score), and
- an apples-to-apples 11-point shared-clock intraday curve score for S129 vs S131 using the SAME
  actual MBO grid samples already captured by S131.

It does not change any forecast or frozen artifact.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
NS = HERE / "forecasts" / "frankie_g3_s131_corrected_reblind"
FROZEN = NS / "grp3_s131_blind_frozen.json"
S129_DIR = HERE / "forecasts" / "frankie_g3_s129_chatgpt_current"
S129_SCORE = S129_DIR / "g3_s129_score.json"
S129_FROZEN = S129_DIR / "g3_s129_current_frankie_blind_frozen.json"
SHARED_CLOCK = [20.0, 22.0, 0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0]


class ReconcileStop(RuntimeError):
    pass


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReconcileStop(f"cannot read {path}: {exc}") from exc


def _metrics(errs):
    a = np.asarray(errs, float)
    return {
        "mae_usd": round(float(np.mean(np.abs(a))), 1),
        "rmse_usd": round(float(math.sqrt(np.mean(a ** 2))), 1),
        "max_abs_error_usd": int(round(float(np.max(np.abs(a))))),
    }


def _sign(x):
    return 1 if x > 0 else (-1 if x < 0 else 0)


def reconcile(score_path: Path):
    s131 = _read(score_path)
    freeze = _read(FROZEN)
    s129s = _read(S129_SCORE)
    s129f = _read(S129_FROZEN)

    current = {r["date"]: r for r in s131["per_day"]}
    frozen = {r["date"]: r for r in freeze["days"]}
    old_score = {r["date"]: r for r in s129s["per_day"]}
    old_frozen = {r["date"]: r for r in s129f["days"]}
    days = list(frozen)
    if not (set(days) == set(current) == set(old_score) == set(old_frozen)):
        raise ReconcileStop("day sets differ across S129/S131 score/freeze records")

    # Prove, do not assume, what S129's endpoint target actually was.
    old_basis_rows = []
    for d in days:
        old_actual = float(old_score[d]["actual"])
        exact_net = float(current[d]["actual_net_usd"])
        exact_day_move = float(current[d]["actual_day_move_usd"])
        if old_actual != exact_net:
            raise ReconcileStop(
                f"S129 basis proof failed on {d}: old actual {old_actual} != exact session net {exact_net}"
            )
        old_basis_rows.append({
            "date": d,
            "s129_actual": old_actual,
            "exact_session_net_usd": exact_net,
            "exact_full_day_move_usd": exact_day_move,
            "actual_gap_usd": current[d]["actual_gap_usd"],
        })

    session_errors = []
    session_hits = 0
    session_call_hits = 0
    n_calls = 0
    full_day_errors = []
    for d in days:
        fr = frozen[d]
        cur = current[d]
        pred_day = float(fr["guess_day_move_usd"])
        pred_gap = float(fr["overnight_gap_usd"])
        pred_net = pred_day - pred_gap
        act_net = float(cur["actual_net_usd"])
        act_day = float(cur["actual_day_move_usd"])
        session_errors.append(pred_net - act_net)
        full_day_errors.append(pred_day - act_day)
        hit = _sign(pred_net) == _sign(act_net)
        session_hits += int(hit)
        if str(fr["disposition"]).upper() == "CALL":
            n_calls += 1
            session_call_hits += int(hit)

    # Same actual point samples, same eleven timestamps, both forecast paths.
    old_curve_err = []
    new_curve_err = []
    per_day_curve = []
    for d in days:
        actual_by_hour = {}
        current_pred_by_hour = {}
        for p in current[d]["grid_points"]:
            # ISO timestamp always carries the correct ET hour; parse without a datetime dependency.
            hh = float(p["timestamp_et"].split("T", 1)[1][:2])
            if hh in SHARED_CLOCK:
                actual_by_hour[hh] = float(p["actual_cum_from_open_usd"])
                current_pred_by_hour[hh] = float(p["forecast_cum_from_open_usd"])

        # S129's first eleven points are exactly 20,22,0,...16. Its later 18/20 tail has no common
        # S131 point and is deliberately excluded from this common-clock comparison.
        old_path = old_frozen[d]["path_p50_curve"][:11]
        old_pred_by_hour = {float(h) % 24.0: float(v) for h, v in old_path}
        if sorted(actual_by_hour) != sorted(SHARED_CLOCK):
            raise ReconcileStop(f"missing shared actual clock point(s) on {d}: {sorted(actual_by_hour)}")
        oe = [old_pred_by_hour[h] - actual_by_hour[h] for h in SHARED_CLOCK]
        ne = [current_pred_by_hour[h] - actual_by_hour[h] for h in SHARED_CLOCK]
        old_curve_err.extend(oe)
        new_curve_err.extend(ne)
        per_day_curve.append({
            "date": d,
            "s129_common_grid_mae_usd": round(float(np.mean(np.abs(oe))), 1),
            "s131_common_grid_mae_usd": round(float(np.mean(np.abs(ne))), 1),
        })

    old_common = _metrics(old_curve_err)
    new_common = _metrics(new_curve_err)
    session = _metrics(session_errors)
    full_day = _metrics(full_day_errors)
    result = {
        "group": "g3_s131_score_reconciled",
        "basis_proof": {
            "verdict": "S129 reported endpoint actual == exact NGV25 session open-to-close net on all 10 days",
            "therefore": "compare S129 endpoint metrics only with S131 session-net metrics; do not compare them with S131 full-day metrics including gaps",
            "rows": old_basis_rows,
        },
        "s131_full_day_endpoint": {
            **full_day,
            "direction_hits": s131["endpoint"]["direction_hits"],
            "n_days": 10,
            "definition": "forecast guessed day move including forecast gap vs actual prior-close-to-close day move",
        },
        "s131_session_net_endpoint": {
            **session,
            "direction_hits": session_hits,
            "n_days": 10,
            "call_direction_hits": session_call_hits,
            "n_calls": n_calls,
            "definition": "forecast curve terminal = guessed day move - forecast gap, vs actual open-to-close session net",
        },
        "s129_reported_session_net_endpoint": {
            "mae_usd": s129s["endpoint_mae_usd"],
            "rmse_usd": s129s["endpoint_rmse_usd"],
            "max_abs_error_usd": s129s["max_abs_endpoint_error_usd"],
            "direction_hits": s129s["p50_direction_hits"],
            "n_days": s129s["n_days"],
            "call_direction_hits": s129s["call_direction_hits"],
            "n_calls": s129s["n_calls"],
        },
        "apples_to_apples_endpoint_delta_s131_minus_s129": {
            "mae_usd": round(session["mae_usd"] - float(s129s["endpoint_mae_usd"]), 1),
            "rmse_usd": round(session["rmse_usd"] - float(s129s["endpoint_rmse_usd"]), 1),
            "max_abs_error_usd": int(session["max_abs_error_usd"] - int(s129s["max_abs_endpoint_error_usd"])),
            "direction_hits": session_hits - int(s129s["p50_direction_hits"]),
        },
        "shared_11_point_intraday_curve": {
            "clock_et": SHARED_CLOCK,
            "points_per_run": len(old_curve_err),
            "s129": old_common,
            "s131": new_common,
            "delta_s131_minus_s129": {
                "mae_usd": round(new_common["mae_usd"] - old_common["mae_usd"], 1),
                "rmse_usd": round(new_common["rmse_usd"] - old_common["rmse_usd"], 1),
            },
            "per_day": per_day_curve,
            "note": "Same exact NGV25 actual samples and same 20,22,0,2,...16 timestamps. S129's extra 18/20 tail and S131's 17 point are excluded. This is the clean curve comparison.",
        },
        "reported_noncommon_curve_metrics": {
            "s129_reported_day_local_mae_usd": s129s["day_local_intraday_curve_mae_usd"],
            "s131_full_12_point_day_local_mae_usd": s131["curve"]["day_local_mae_usd"],
            "warning": "Do not subtract these as a clean improvement delta; the clocks/method differ. Use shared_11_point_intraday_curve above.",
        },
        "verdict_rule": "No forecast mutation after reveal. This file only reconciles measurement definitions."
    }
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--score", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    try:
        r = reconcile(args.score)
        args.out.write_text(json.dumps(r, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({
            "basis": r["basis_proof"]["verdict"],
            "s131_session_net": r["s131_session_net_endpoint"],
            "s129_session_net": r["s129_reported_session_net_endpoint"],
            "endpoint_delta": r["apples_to_apples_endpoint_delta_s131_minus_s129"],
            "shared_curve": r["shared_11_point_intraday_curve"],
        }, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
