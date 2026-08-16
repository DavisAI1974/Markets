#!/usr/bin/env python3
"""S134 full-refine runner repairs for event-driven node time semantics.

Two mechanical issues existed outside the refine logic itself:
1. adaptive-node de-duplication could replace the already-zeroed reopen node before S132 validation;
2. fit/render code rebuilt fractional ET hours at minute precision, so a real 20:00:15 node collapsed
   onto 20:00:00 and could incorrectly advance the rest of that session by a calendar day.

This runner keeps S134's target-tape-selected nodes and values intact. It re-applies the cumulative
open anchor immediately before validation, then recomputes reconstruction fit and rendering with
second-precision wall-clock unwrapping. No brain, role, play, curve value, target tape, or lesson is
changed.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import frankie_g3_s134_full_refine as s134

ET = s134.ET
MULT = s134.MULT
_original_validate = s134.s132.validate_day


def _validate_after_dedup(payload, gid, day, spec):
    nodes = payload.get("curve_nodes")
    path = payload.get("path_p50_curve")
    if isinstance(nodes, list) and nodes:
        first = nodes[0]
        if isinstance(first, dict):
            first["p25_cum_usd"] = 0.0
            first["p50_cum_usd"] = 0.0
            first["p75_cum_usd"] = 0.0
    if isinstance(path, list) and path and isinstance(path[0], list) and len(path[0]) >= 2:
        path[0][1] = 0.0
    return _original_validate(payload, gid, day, spec)


def _node_datetimes(day: str, nodes: list[dict]) -> list[pd.Timestamp]:
    """Unwrap ET wall-clock nodes over one session without rounding away seconds."""
    target_date = pd.Timestamp(f"{day[:4]}-{day[4:6]}-{day[6:]}", tz=ET)
    first_h = float(nodes[0]["et_hour"])
    cur_date = (target_date - pd.Timedelta(days=1)).date() if first_h >= 18.0 else target_date.date()
    prev_h = None
    out = []
    for n in nodes:
        h = float(n["et_hour"])
        if prev_h is not None and h < prev_h:
            cur_date = (pd.Timestamp(cur_date) + pd.Timedelta(days=1)).date()
        seconds = int(round(h * 3600.0))
        if seconds >= 24 * 3600:
            seconds = 24 * 3600 - 1
        t = pd.Timestamp(cur_date, tz=ET) + pd.Timedelta(seconds=seconds)
        if out and t <= out[-1]:
            t = out[-1] + pd.Timedelta(seconds=1)
        out.append(t)
        prev_h = h
    return out


def _actual_rows() -> list[dict]:
    s134.g3.install_g3_context()
    import group_mbo_engine as mbo
    prior = float(s134.g3.ANCHOR_PRICE)
    rows = []
    for day in s134.g3.DAYS:
        ev = mbo.per_day_evidence("g3", day)
        gap = round((float(ev["open"]) - prior) * MULT)
        rows.append({
            "date": day,
            "open": ev["open"],
            "close": ev["close"],
            "gap_usd": gap,
            "net_usd": ev["net_usd"],
            "day_move_usd": gap + int(ev["net_usd"]),
        })
        prior = float(ev["close"])
    return rows


def _recompute_fit(obj: dict, actual_rows: list[dict]) -> None:
    act = pd.DataFrame(obj["actual_plot_one_minute"], columns=["ts", "price"])
    act["dt"] = pd.to_datetime(act["ts"], unit="s", utc=True).dt.tz_convert(ET)
    amap = {r["date"]: r for r in actual_rows}
    fits = []
    for d in obj["days"]:
        day = d["date"]
        ndt = _node_datetimes(day, d["curve_nodes"])
        open_px = float(amap[day]["open"])
        m = act[(act["dt"] >= ndt[0]) & (act["dt"] <= ndt[-1])]
        if m.empty:
            raise RuntimeError(f"S134 {day}: no actual one-minute tape inside refined node window")
        nx = np.array([(t - ndt[0]).total_seconds() for t in ndt], float)
        ny = np.array([float(n["p50_cum_usd"]) for n in d["curve_nodes"]], float)
        mx = np.array([(t - ndt[0]).total_seconds() for t in m["dt"]], float)
        actual_local = (m["price"].to_numpy(float) - open_px) * MULT
        pred = np.interp(mx, nx, ny)
        err = pred - actual_local
        fits.append({
            "date": day,
            "node_count": len(d["curve_nodes"]),
            "one_minute_points": int(len(err)),
            "mae_usd": round(float(np.mean(np.abs(err))), 1),
            "rmse_usd": round(float(math.sqrt(np.mean(err ** 2))), 1),
            "max_abs_error_usd": round(float(np.max(np.abs(err))), 1),
        })
    obj["reconstruction_fit"] = {
        "per_day": fits,
        "mean_day_mae_usd": round(float(np.mean([x["mae_usd"] for x in fits])), 1),
        "pooled_day_rmse_usd": round(float(math.sqrt(np.mean([x["rmse_usd"] ** 2 for x in fits]))), 1),
        "metric_note": "post-reveal adaptive reconstruction against exact NGV25 one-minute tape; second-precision event-node timestamps; diagnostic only",
    }


def _render(obj: dict, actual_rows: list[dict], out: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    act = pd.DataFrame(obj["actual_plot_one_minute"], columns=["ts", "price"])
    act["dt"] = pd.to_datetime(act["ts"], unit="s", utc=True).dt.tz_convert(ET)
    amap = {r["date"]: r for r in actual_rows}

    fig, ax = plt.subplots(figsize=(16, 7.5))
    x = act["dt"].to_list(); y = act["price"].to_list()
    bx, by = [], []
    for i, (t, p) in enumerate(zip(x, y)):
        if i and (t - x[i - 1]).total_seconds() > 3 * 3600:
            bx.append(t); by.append(float("nan"))
        bx.append(t); by.append(p)
    ax.plot(bx, by, linewidth=0.8, label="actual NGV25")

    for d in obj["days"]:
        day = d["date"]
        ndt = _node_datetimes(day, d["curve_nodes"])
        open_px = float(amap[day]["open"])
        p50 = [open_px + float(n["p50_cum_usd"]) / MULT for n in d["curve_nodes"]]
        p25 = [open_px + float(n["p25_cum_usd"]) / MULT for n in d["curve_nodes"]]
        p75 = [open_px + float(n["p75_cum_usd"]) / MULT for n in d["curve_nodes"]]
        ax.fill_between(ndt, p25, p75, alpha=0.10)
        ax.plot(ndt, p50, marker="o", markersize=3.2, linewidth=1.15)

    ax.set_title("G3 S134 full two-week Frankie refine: event-driven reconstruction vs actual NGV25")
    ax.set_ylabel("price ($/MMBtu)")
    ax.grid(True, alpha=0.22)
    fig.autofmt_xdate()
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=150)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    s134.s132.validate_day = _validate_after_dedup
    obj = s134.build()
    rows = _actual_rows()
    obj["actual_days"] = rows
    _recompute_fit(obj, rows)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    j = args.out_dir / "g3_s134_full_refine.json"
    j.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _render(obj, rows, args.out_dir / "g3_s134_refined_vs_actual.png")
    print(json.dumps({
        "status": "READY",
        "days": len(obj["days"]),
        "nodes": sum(len(d["curve_nodes"]) for d in obj["days"]),
        "mean_day_mae_usd": obj["reconstruction_fit"]["mean_day_mae_usd"],
        "out": str(j),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
