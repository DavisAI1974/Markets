#!/usr/bin/env python3
"""Post-freeze S131 reveal/score for current-Frankie G3 replay.

HARD ORDERING: this script refuses to run unless the immutable S131 blind freeze exists in git and
has the exact CI-promoted SHA256. Only after that check does it touch AWS or target-window actuals.

Actual source: the same exact per-contract NGV25 MBO day files used by the canonical group_actual
engine.  Endpoint scoring uses ``group_actual.build``.  Curve scoring samples the actual scored-leg
trade tape at each of the 120 frozen P50 timestamps and reports both:
- absolute-price curve error (does the chained full block sit at the right level?), and
- day-local cum-from-open curve error (does each specialist draw the right intraday shape?).

No refine, no brain edit, no hydration and no forecast mutation occurs here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import frankie_g3_reblind_s131 as s131

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GID = "g3"
DAYS = list(s131.DAYS)
FROZEN = HERE / "forecasts" / s131.DEFAULT_NAMESPACE / "grp3_s131_blind_frozen.json"
EXPECTED_FREEZE_SHA256 = "3368822121b9c515891c83cb5b3d0a4d85881acff7f3d57cc1e7189870836771"
S129_SCORE = HERE / "forecasts" / "frankie_g3_s129_chatgpt_current" / "g3_s129_score.json"


class ScoreStop(RuntimeError):
    pass


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _read(path: Path) -> dict[str, Any]:
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoreStop(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(obj, dict):
        raise ScoreStop(f"expected object: {path}")
    return obj


def _assert_frozen() -> dict[str, Any]:
    if not FROZEN.is_file():
        raise ScoreStop(f"immutable S131 freeze is absent: {FROZEN}")
    got = _sha(FROZEN)
    if got != EXPECTED_FREEZE_SHA256:
        raise ScoreStop(
            f"immutable S131 freeze hash mismatch: expected {EXPECTED_FREEZE_SHA256}, got {got}"
        )
    d = _read(FROZEN)
    if d.get("phase") != "BLIND_FROZEN_BEFORE_REVEAL":
        raise ScoreStop(f"unexpected frozen phase: {d.get('phase')!r}")
    if d.get("actuals_read") is not False or d.get("target_window_outcomes_read") is not False:
        raise ScoreStop("freeze does not certify pre-reveal outcome isolation")
    if len(d.get("days") or []) != 10 or len(d.get("full_curve_p50") or []) != 120:
        raise ScoreStop("freeze cardinality changed")
    return d


def _stage_actual_leg_files() -> dict[str, Any]:
    """Pull only the exact scored-contract MBO objects required to reveal the frozen block."""
    s131.install_g3_context()
    import stage_group as sg

    os.makedirs(sg.LEG_DIR, exist_ok=True)
    rows = []
    for day in DAYS:
        store = s131.gc.leg_for(GID, day)
        key = f"nymex/{store}/NG_{day}.dbn.zst"
        dest = os.path.join(sg.LEG_DIR, f"{store}_{day}.dbn.zst")
        status = sg._dl(key, dest)
        if str(status).startswith("miss"):
            raise ScoreStop(f"actual reveal leg missing for {day}: {status}")
        rows.append({"day": day, "store": store, "status": status})
    return {"actuals_read": True, "source": "exact per-contract scored-leg MBO", "files": rows}


def _nearest_price(ts: np.ndarray, px: np.ndarray, target: float) -> tuple[float, float]:
    if ts.size == 0:
        raise ScoreStop("cannot sample empty actual tape")
    i = int(np.searchsorted(ts, target))
    cand = []
    if i < ts.size:
        cand.append(i)
    if i > 0:
        cand.append(i - 1)
    j = min(cand, key=lambda k: abs(float(ts[k]) - target))
    return float(px[j]), abs(float(ts[j]) - target)


def _sign(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


def _render(actual: dict[str, Any], frozen: dict[str, Any], out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import render_util as ru

    at = [float(t) for t, _ in actual["continuous"]]
    ap = [float(p) for _, p in actual["continuous"]]
    bt, bp = ru.break_gaps(at, ap)
    adt = pd.to_datetime(bt, unit="s", utc=True).tz_convert("America/New_York")

    fx = [pd.Timestamp(p["timestamp_et"]) for p in frozen["full_curve_p50"]]
    fy = [float(p["price_p50"]) for p in frozen["full_curve_p50"]]

    fig, ax = plt.subplots(figsize=(15, 7))
    ax.plot(adt, bp, lw=0.9, label="actual NGV25 MBO")
    ru.plot_forecast(ax, fx, fy, color="#d1242f", label="S131 current-Frankie frozen P50", lw=1.35, z=4)
    ax.axhline(float(frozen["anchor"]["close"]), lw=0.7, ls="--")
    ax.set_title("NG G3 S131 current-Frankie historical replay: frozen full curve vs actual")
    ax.set_ylabel("price ($/MMBtu)")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=140)
    plt.close(fig)


def score(out_dir: Path) -> dict[str, Any]:
    frozen = _assert_frozen()  # MUST happen before any target actual access.
    stage = _stage_actual_leg_files()

    import group_actual as ga
    # Avoid parsing every DBN twice: canonical actual build and curve scoring share one exact cache.
    original_load = ga.load_trades
    cache: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}

    def cached(store: str, day: str):
        key = (store, day)
        if key not in cache:
            cache[key] = original_load(store, day)
        return cache[key]

    ga.load_trades = cached
    actual = ga.build(GID)
    amap = {r["date"]: r for r in actual["days"]}
    fdays = {r["date"]: r for r in frozen["days"]}
    if set(amap) != set(DAYS) or set(fdays) != set(DAYS):
        raise ScoreStop(f"day coverage mismatch actual={sorted(amap)} frozen={sorted(fdays)}")

    per_day = []
    endpoint_errors = []
    direction_hits = 0
    call_hits = 0
    n_calls = 0
    abstain_actual_abs = []
    local_curve_errors: list[float] = []
    absolute_curve_errors: list[float] = []
    sample_lags: list[float] = []

    curve_by_day: dict[str, list[dict[str, Any]]] = {d: [] for d in DAYS}
    for p in frozen["full_curve_p50"]:
        curve_by_day[p["date"]].append(p)

    for day in DAYS:
        fr = fdays[day]
        ar = amap[day]
        guess = float(fr["guess_day_move_usd"])
        act = float(ar["day_move_usd"])
        err = guess - act
        endpoint_errors.append(err)
        hit = _sign(guess) == _sign(act)
        direction_hits += int(hit)
        is_call = str(fr["disposition"]).upper() == "CALL"
        if is_call:
            n_calls += 1
            call_hits += int(hit)
        else:
            abstain_actual_abs.append(abs(act))

        store = ar["leg"]
        ts, px = cached(store, day)
        if px.size == 0:
            raise ScoreStop(f"actual tape empty for {day}")
        session_open = float(px[0])
        day_local = []
        day_absolute = []
        point_rows = []
        for p in curve_by_day[day]:
            target = pd.Timestamp(p["timestamp_et"]).timestamp()
            actual_px, lag = _nearest_price(ts, px, target)
            actual_local = (actual_px - session_open) * s131.gc.MULT
            pred_local = float(p["cum_from_open_usd"])
            le = pred_local - actual_local
            ae = (float(p["price_p50"]) - actual_px) * s131.gc.MULT
            local_curve_errors.append(le)
            absolute_curve_errors.append(ae)
            sample_lags.append(lag)
            day_local.append(le)
            day_absolute.append(ae)
            point_rows.append({
                "timestamp_et": p["timestamp_et"],
                "forecast_price": p["price_p50"],
                "actual_price": round(actual_px, 6),
                "forecast_cum_from_open_usd": pred_local,
                "actual_cum_from_open_usd": round(actual_local, 1),
                "local_error_usd": round(le, 1),
                "absolute_error_usd": round(ae, 1),
                "nearest_trade_lag_seconds": round(lag, 3),
            })

        per_day.append({
            "date": day,
            "owner": fr["owner"],
            "disposition": fr["disposition"],
            "forecast_day_move_usd": fr["guess_day_move_usd"],
            "actual_day_move_usd": ar["day_move_usd"],
            "endpoint_error_usd": int(err) if err.is_integer() else err,
            "abs_endpoint_error_usd": int(abs(err)) if abs(err).is_integer() else abs(err),
            "direction_hit": hit,
            "actual_open": ar["open"],
            "actual_close": ar["close"],
            "actual_gap_usd": ar["gap_usd"],
            "actual_net_usd": ar["net_usd"],
            "day_local_curve_mae_usd": round(float(np.mean(np.abs(day_local))), 1),
            "absolute_curve_mae_usd": round(float(np.mean(np.abs(day_absolute))), 1),
            "grid_points": point_rows,
        })

    ee = np.asarray(endpoint_errors, float)
    lc = np.asarray(local_curve_errors, float)
    ac = np.asarray(absolute_curve_errors, float)
    legacy = _read(S129_SCORE)
    current_endpoint = {
        "mae_usd": round(float(np.mean(np.abs(ee))), 1),
        "rmse_usd": round(float(math.sqrt(np.mean(ee ** 2))), 1),
        "max_abs_error_usd": int(round(float(np.max(np.abs(ee))))),
        "direction_hits": direction_hits,
        "n_days": len(DAYS),
        "call_direction_hits": call_hits,
        "n_calls": n_calls,
        "n_abstains": len(DAYS) - n_calls,
        "abstain_mean_abs_actual_move_usd": (
            round(float(np.mean(abstain_actual_abs)), 1) if abstain_actual_abs else None
        ),
    }
    current_curve = {
        "points": len(lc),
        "day_local_mae_usd": round(float(np.mean(np.abs(lc))), 1),
        "day_local_rmse_usd": round(float(math.sqrt(np.mean(lc ** 2))), 1),
        "absolute_price_mae_usd": round(float(np.mean(np.abs(ac))), 1),
        "absolute_price_rmse_usd": round(float(math.sqrt(np.mean(ac ** 2))), 1),
        "max_nearest_trade_lag_seconds": round(max(sample_lags), 3),
        "sampling": "nearest scored-leg MBO trade to each frozen canonical timestamp",
    }
    comparison = {
        "s129_endpoint_mae_usd": legacy["endpoint_mae_usd"],
        "s131_endpoint_mae_usd": current_endpoint["mae_usd"],
        "endpoint_mae_delta_usd": round(current_endpoint["mae_usd"] - float(legacy["endpoint_mae_usd"]), 1),
        "s129_endpoint_rmse_usd": legacy["endpoint_rmse_usd"],
        "s131_endpoint_rmse_usd": current_endpoint["rmse_usd"],
        "endpoint_rmse_delta_usd": round(current_endpoint["rmse_usd"] - float(legacy["endpoint_rmse_usd"]), 1),
        "s129_direction_hits": legacy["p50_direction_hits"],
        "s131_direction_hits": current_endpoint["direction_hits"],
        "s129_call_direction_hits": legacy["call_direction_hits"],
        "s129_n_calls": legacy["n_calls"],
        "s131_call_direction_hits": current_endpoint["call_direction_hits"],
        "s131_n_calls": current_endpoint["n_calls"],
        "s129_reported_day_local_curve_mae_usd": legacy["day_local_intraday_curve_mae_usd"],
        "s131_day_local_curve_mae_usd": current_curve["day_local_mae_usd"],
        "curve_metric_note": "S129's reported curve metric is retained as its frozen historical score. S131 uses exact nearest-trade scoring on the current canonical 12-point clock; clocks differ, so treat the curve-MAE delta as indicative, not byte-identical methodology.",
    }

    result = {
        "group": "g3_s131_current_frankie_corrected",
        "phase": "POST_FREEZE_REVEAL_SCORE",
        "classification": "current-Frankie historical improvement replay; not pristine holdout",
        "frozen_sha256": _sha(FROZEN),
        "frozen_before_actual_access": True,
        "actuals_read": True,
        "hydration": "REJECTED_NOT_USED",
        "actual_source": stage,
        "endpoint": current_endpoint,
        "curve": current_curve,
        "terminal": {
            "forecast_cum_from_anchor_usd": frozen["summary"]["terminal_cum_usd"],
            "actual_cum_from_anchor_usd": actual["days"][-1]["cum_from_anchor_usd"],
            "forecast_terminal_price": frozen["summary"]["terminal_price_p50"],
            "actual_terminal_price": actual["days"][-1]["close"],
        },
        "comparison_to_s129_sparse_runner": comparison,
        "per_day": per_day,
        "interpretation_rule": "Score the frozen current-Frankie output as-is. Do not rewrite specialist calls after reveal. Any brain lesson belongs in a separate post-score proposal phase.",
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "g3_s131_actual.json").write_text(
        json.dumps(actual, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "g3_s131_score.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _render(actual, frozen, out_dir / "g3_s131_current_vs_actual.png")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    try:
        result = score(args.out)
        print(json.dumps({
            "status": "S131_SCORED_AFTER_FREEZE",
            "endpoint": result["endpoint"],
            "curve": result["curve"],
            "terminal": result["terminal"],
            "comparison_to_s129_sparse_runner": result["comparison_to_s129_sparse_runner"],
        }, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"STOP - {type(exc).__name__}: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
