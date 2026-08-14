#!/usr/bin/env python3
"""Render g24 full actual RT vs immutable S127 blind vs S128 causal refine."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import group_config as gc

HERE = Path(__file__).resolve().parent
R = HERE / "renders" / "ng_refine_s95"
F = HERE / "forecasts"
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")
MULT = 10000.0


def read(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def session_pos(raw) -> float:
    h = float(raw)
    if abs(h - 24.0) < 1e-12:
        return 24.0
    return h - 20.0 if h >= 20.0 else h + 4.0


def with_closure_breaks(cont):
    xs, ys = [], []
    prev = None
    for t, px in cont:
        dt = datetime.fromtimestamp(float(t), tz=UTC).astimezone(ET)
        if prev is not None and (dt - prev).total_seconds() > 3 * 3600:
            xs.append(prev + timedelta(seconds=1)); ys.append(float("nan"))
        xs.append(dt); ys.append(float(px)); prev = dt
    return xs, ys


def day_start(day: str) -> datetime:
    d = datetime.strptime(day, "%Y%m%d")
    return datetime(d.year, d.month, d.day, 20, 0, tzinfo=ET) - timedelta(days=1)


def main() -> int:
    actual = read(R / "g24_actual.json")
    refined = read(F / "grp24_mbo_refined.json")
    owners = gc.owner_map("g24")
    actual_by_day = {str(d["date"]): d for d in actual["days"]}

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    ax_x, ax_y = with_closure_breaks(actual["continuous"])
    bx, by, rx, ry = [], [], [], []

    for row in refined["days"]:
        day = str(row["date"])
        a = actual_by_day[day]
        prior_close = float(a["open"]) - float(a.get("gap_usd", 0) or 0) / MULT
        start = day_start(day)

        # Immutable blind: gap is separate; path is ex-gap cumulative from the reopen.
        owner = owners[day]
        b = read(F / "frankie_g24_s127_chatgpt" / f"grp24_{owner}_{day}.json")
        bgap = float(b.get("overnight_gap_usd", 0) or 0)
        for raw_t, move in b["path_p50_curve"]:
            bx.append(start + timedelta(hours=session_pos(raw_t)))
            by.append(prior_close + (bgap + float(move)) / MULT)
        bx.append(start + timedelta(hours=24, seconds=1)); by.append(float("nan"))

        # Refine path is cumulative day-move from the prior close, including realized reopen gap.
        for raw_t, move in row["path_p50"]:
            rx.append(start + timedelta(hours=session_pos(raw_t)))
            ry.append(prior_close + float(move) / MULT)
        rx.append(start + timedelta(hours=24, seconds=1)); ry.append(float("nan"))

    fig, ax = plt.subplots(figsize=(18, 7))
    ax.plot(ax_x, ax_y, lw=0.9, label="actual RT")
    ax.plot(bx, by, lw=1.2, ls="--", alpha=0.75, label="S127 blind p50")
    ax.plot(rx, ry, lw=1.9, marker="o", markersize=2.6, label="S128 refined p50")

    seam = str(actual.get("seam") or "")
    if seam:
        d = datetime.strptime(seam, "%Y%m%d")
        seam_dt = datetime(d.year, d.month, d.day, 0, 0, tzinfo=ET)
        ax.axvline(seam_dt, lw=1.0, ls="-.", alpha=0.8)
        ax.text(seam_dt, min(ax_y), " Q26→U26 scoring seam", fontsize=8, va="bottom")

    ymax = max(ax_y)
    for row in refined["days"]:
        day = str(row["date"])
        d = datetime.strptime(day, "%Y%m%d")
        mark = datetime(d.year, d.month, d.day, 12, 0, tzinfo=ET)
        a = row["actual_day_move_usd"]
        b = row["blind_day_move_usd"]
        r = row["refined_day_move_usd"]
        ax.text(mark, ymax, f"{day[4:6]}-{day[6:]} {row['owner']}\nB {b:+.0f} / R {r:+.0f} / A {a:+.0f}", fontsize=7, va="top", ha="center")

    ax.set_title(
        "Frankie g24 S128 — Full RT vs immutable blind vs chronological causal refine\n"
        f"Refine MAE ${refined['mean_abs_err_usd']} | max error ${refined['max_abs_err_usd']} | direction {refined['dir_hits']}/{refined['n']} | target <= ${refined['target_abs_error_usd']}"
    )
    ax.set_ylabel("NG price")
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=1, tz=ET))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d", tz=ET))
    ax.tick_params(axis="x", labelrotation=45, labelsize=8)
    ax.grid(True, alpha=0.25)
    ax.legend(loc="lower right")
    fig.tight_layout()
    out = R / "g24_frankie_s128_refined_vs_actual.png"
    fig.savefig(out, dpi=160, bbox_inches="tight")
    plt.close(fig)

    metrics = {
        "group": "g24",
        "phase": refined["phase"],
        "mae_usd": refined["mean_abs_err_usd"],
        "max_abs_err_usd": refined["max_abs_err_usd"],
        "direction_hits": refined["dir_hits"],
        "n": refined["n"],
        "target_abs_error_usd": refined["target_abs_error_usd"],
        "all_days_within_target": all(abs(float(d["refined_err_usd"])) <= float(refined["target_abs_error_usd"]) for d in refined["days"]),
        "endpoint_rule": refined["endpoint_reconstruction_rule"],
    }
    (R / "g24_frankie_s128_refine_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"render": str(out.relative_to(HERE)), "metrics": metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
