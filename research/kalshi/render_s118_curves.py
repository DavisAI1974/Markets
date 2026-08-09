#!/usr/bin/env python3
"""render_s118_curves.py - the S118 forward-curve renders: actual vs old blind vs Frankie.

D32: THE PRODUCT IS A CURVE. Daily direction is a dashboard number; the integrated path is what a
trade is taken against, so the render is cum-from-anchor, not per-day bars.

RENDER RULE (S104/S105, and both halves matter):
  - the ACTUAL curve and each forecaster's OWN p50 path, nothing re-anchored or rescaled;
  - NO WEEKEND BRIDGE. A straight segment across a Friday->Monday gap draws a move that never
    traded. Every line breaks at the seam instead (`break_gaps`), which is why the weekend shows as
    a gap rather than a slope.

Every series here starts at the same declared anchor and accumulates that series' OWN day moves, so
the vertical distance between two lines on any day IS the cumulative error to that day - no other
transformation is applied.

    python render_s118_curves.py
"""
from __future__ import annotations

import datetime
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCORES = os.path.join(HERE, "records", "S118", "frankie_s118_b_scores.json")
OUTDIR = os.path.join(HERE, "records", "S118")


def _d(ymd):
    return datetime.date(int(ymd[:4]), int(ymd[4:6]), int(ymd[6:8]))


def _segments(days, vals):
    """Split into contiguous runs, breaking wherever the calendar gap exceeds one day.

    This is `break_gaps`. Joining across a weekend draws a line through hours the market never
    traded, and a reader takes slope off that line."""
    segs, cur_d, cur_v = [], [], []
    for i, day in enumerate(days):
        if cur_d and (_d(day) - _d(cur_d[-1])).days > 1:
            segs.append((cur_d, cur_v))
            cur_d, cur_v = [], []
        cur_d.append(day)
        cur_v.append(vals[i])
    if cur_d:
        segs.append((cur_d, cur_v))
    return segs


def render(group, events, anchor_price):
    days = [e["day"] for e in events]
    series = {}
    for name, key in (("actual", "actual"), ("old blind", "old_blind"), ("Frankie", "frankie")):
        cum, run = [], 0.0
        for e in events:
            run += float(e[key])
            cum.append(run)
        series[name] = cum

    style = {"actual": dict(color="#111111", lw=2.6, marker="o", ms=5, zorder=3),
             "old blind": dict(color="#c2703a", lw=1.8, marker="s", ms=4, ls="--", zorder=2),
             "Frankie": dict(color="#2f6fa8", lw=1.8, marker="^", ms=4, ls="-.", zorder=2)}

    fig, ax = plt.subplots(figsize=(11, 5.6))
    xs = list(range(len(days)))
    for name, cum in series.items():
        first = True
        for seg_days, seg_vals in _segments(days, cum):
            idx = [days.index(d) for d in seg_days]
            ax.plot(idx, seg_vals, label=name if first else None, **style[name])
            first = False

    ax.axhline(0, color="#999999", lw=0.8)
    for i, day in enumerate(days):
        if i and (_d(day) - _d(days[i - 1])).days > 1:
            ax.axvspan(i - 0.5, i - 0.42, color="#dddddd", zorder=0)

    ax.set_xticks(xs)
    ax.set_xticklabels(["%s\n%s" % (d[4:6] + "/" + d[6:8], _d(d).strftime("%a")) for d in days],
                       fontsize=8)
    ax.set_ylabel("cum from anchor (USD per contract)")
    ax.set_title("%s - forward curve from anchor %.3f   (actual vs old blind vs Frankie, S118)\n"
                 "weekend gaps are BREAKS, not segments - no line is drawn through untraded hours"
                 % (group.upper(), anchor_price), fontsize=10)
    ax.legend(loc="best", fontsize=9)
    ax.grid(alpha=0.25, lw=0.6)

    # Name the largest actual moves on the chart itself, so the picture cannot be read without them
    # (D37: the big events are the ones that decide whether a candidate helped).
    big = sorted(events, key=lambda e: -abs(e["actual"]))[:3]
    for e in big:
        i = days.index(e["day"])
        ax.annotate("%+d actual\nF %+d / old %+d" % (e["actual"], e["frankie"], e["old_blind"]),
                    xy=(i, series["actual"][i]), xytext=(0, 16 if e["actual"] > 0 else -34),
                    textcoords="offset points", ha="center", fontsize=7, color="#444444")

    out = os.path.join(OUTDIR, "%s_s118_curve.png" % group)
    plt.tight_layout()
    plt.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out


def main():
    with open(SCORES, encoding="utf-8") as f:
        data = json.load(f)
    import group_config as gc
    made = []
    for s in data["scores"]:
        gid = s["group"]
        made.append(render(gid, s["events"], gc.GROUPS[gid]["anchor"]))
    for p in made:
        print("wrote", os.path.relpath(p, HERE))


if __name__ == "__main__":
    main()
