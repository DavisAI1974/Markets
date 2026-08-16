"""Match NG dipole onset->exhaustion curves to actual leg duration classes.

Retrospective structural audit only. Duration classes are within-day tertiles for each
ZigZag threshold, so 'very short/short/long' is not tied to fees or an imported crypto cutoff.
The normalized curve is descriptive (future leg end is used only to place fractional-age points),
while the separate runway audit remains the causal fixed-age test.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import median

from ng_dipole_runway_audit import (
    THRESH_TICKS, load_day, zigzag_legs, flow_imb, book_state, mean, quantile
)

FRACS = (0.0, 0.10, 0.25, 0.50, 0.75, 1.0)
CLASSES = ("very_short", "short", "long")


def cls_for(duration, q1, q2):
    if duration <= q1:
        return "very_short"
    if duration <= q2:
        return "short"
    return "long"


def state(day, src, t):
    return flow_imb(day, t) if src == "flow" else book_state(day, t)


def day_threshold(day, threshold, src):
    legs = zigzag_legs(day.price, threshold)
    if len(legs) < 9:
        return {"n_legs": len(legs)}
    ds = [l["duration"] for l in legs]
    q1, q2 = quantile(ds, 1/3), quantile(ds, 2/3)
    buckets = {c: [] for c in CLASSES}
    for l in legs:
        c = cls_for(l["duration"], q1, q2)
        curve = []
        for f in FRACS:
            t = int(round(l["start"] + f * l["duration"]))
            raw = state(day, src, t)
            curve.append(l["dir"] * raw if math.isfinite(raw) else float("nan"))
        if not math.isfinite(curve[0]):
            continue
        buckets[c].append({"duration": l["duration"], "ticks": l["ticks"], "curve": curve})
    out = {"n_legs": len(legs), "duration_tertile_cuts_s": [q1, q2], "classes": {}}
    for c in CLASSES:
        b = buckets[c]
        if not b:
            out["classes"][c] = {"n": 0}
            continue
        mc = []
        medc = []
        for j in range(len(FRACS)):
            vals = [r["curve"][j] for r in b if math.isfinite(r["curve"][j])]
            mc.append(mean(vals))
            medc.append(median(vals) if vals else float("nan"))
        onset = mc[0]
        out["classes"][c] = {
            "n": len(b),
            "median_duration_s": median([r["duration"] for r in b]),
            "mean_duration_s": mean([r["duration"] for r in b]),
            "median_leg_ticks": median([r["ticks"] for r in b]),
            "mean_curve": mc,
            "median_curve": medc,
            "mean_dive_from_onset": [onset - x for x in mc],
        }
    return out


def main(paths):
    days = [load_day(p) for p in paths]
    out = {
        "definition": {
            "classes": "within-day duration tertiles per ZigZag threshold: very_short / short / long",
            "fractions_of_leg_life": FRACS,
            "flow": "direction-aligned 60s signed trade-volume imbalance, trade sign from price vs concurrent midpoint",
            "book": "direction-aligned 60s mean 10-level MBP imbalance",
            "important": "normalized curves are retrospective geometry; fixed-age runway audit is the causal/live test",
        },
        "days": {},
        "equal_weight_day": {},
    }
    for d in days:
        out["days"][d.day] = {}
        for src in ("flow", "book"):
            for th in THRESH_TICKS:
                k = f"{src}|{th}t"
                out["days"][d.day][k] = day_threshold(d, th, src)

    for src in ("flow", "book"):
        for th in THRESH_TICKS:
            k = f"{src}|{th}t"
            eq = {"days": 0, "classes": {}}
            usable = [out["days"][d.day][k] for d in days if out["days"][d.day][k].get("classes")]
            eq["days"] = len(usable)
            for c in CLASSES:
                cc = [u["classes"][c] for u in usable if u["classes"].get(c, {}).get("n", 0)]
                if not cc:
                    eq["classes"][c] = {"days": 0}
                    continue
                curves = [[x["mean_curve"][j] for x in cc] for j in range(len(FRACS))]
                dives = [[x["mean_dive_from_onset"][j] for x in cc] for j in range(len(FRACS))]
                eq["classes"][c] = {
                    "days": len(cc),
                    "median_duration_s_mean_across_days": mean([x["median_duration_s"] for x in cc]),
                    "median_leg_ticks_mean_across_days": mean([x["median_leg_ticks"] for x in cc]),
                    "mean_curve_equal_day": [mean(v) for v in curves],
                    "mean_dive_equal_day": [mean(v) for v in dives],
                }
            out["equal_weight_day"][k] = eq

    p = Path("ng_dipole_duration_class_results.json")
    p.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    print(json.dumps(out["equal_weight_day"], indent=2, sort_keys=True))
    print(f"RESULT_FILE={p}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("pass raw NG day files")
    main(sys.argv[1:])
