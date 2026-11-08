"""Does the frozen A state carry price direction once it is knowable?

The A post-state classifier reads t0..+60, so the state is known at t0+60 at the earliest. This script
anchors at t0+60 (and at the archived recognition second where later) and measures, from the price at the
anchor, (1) the direction of the first 3/5/8-tick excursion relative to the burst polarity and (2) the
signed tick change at anchor+60/+300/+600, by A state and by seed state, on every frozen-detector event of
the full October 18 session. Companion to frozen_a_classifier_oct18.py; nothing refit. No trade cost.
"""

import gzip
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402

HORIZONS = (60, 300, 600)
SCALES = (3, 5, 8)


def first_dir(series, a, k, last):
    p0 = series[a]
    if not X.fin(p0):
        return None
    for t in range(a + 1, last + 1):
        v = series[t]
        if X.fin(v) and abs(v - p0) >= k * X.TICK - 1e-9:
            return 1 if v > p0 else -1
    return None


def delta(series, a, h, last):
    if a + h > last or not X.fin(series[a]):
        return None
    v = series[a + h]
    if not X.fin(v):
        return None
    return round((v - series[a]) / X.TICK)


def main():
    stream = X.replay()
    last = min(stream["last_trade"], 86399)
    price = stream["price"]
    cls = {r["t0"]: r for r in (json.loads(l) for l in gzip.open(HERE / "frozen-a-classifier-oct18-events.jsonl.gz", "rt"))}
    ev = [json.loads(l) for l in gzip.open(HERE / "exhaustion-clock-oct18-events.jsonl.gz", "rt")]
    ev = [r for r in ev if r["mode"] == "day"]
    recs = []
    for r in ev:
        t0, pol = r["t0"], r["polarity"]
        c = cls[t0]
        rec_s = r.get("archived_recognition_s")
        anchors = {"plus60": t0 + 60}
        if rec_s is not None:
            anchors["known"] = max(t0 + 60, int(rec_s))
        rec = dict(t0=t0, polarity=pol, seed=r["seed_state"], a_state=c["a_state"])
        for name, a in anchors.items():
            if a > last:
                continue
            for k in SCALES:
                d = first_dir(price, a, k, last)
                rec[f"{name}_first{k}t_with"] = None if d is None else int(d == pol)
            for h in HORIZONS:
                d = delta(price, a, h, last)
                rec[f"{name}_d{h}_oriented"] = None if d is None else pol * d
        recs.append(rec)
    summary = {}
    for group_key in ("a_state", "seed"):
        tab = {}
        for g in sorted({r[group_key] for r in recs}):
            sub = [r for r in recs if r[group_key] == g]
            row = {"n": len(sub)}
            for name in ("plus60", "known"):
                for k in SCALES:
                    vals = [r[f"{name}_first{k}t_with"] for r in sub if r.get(f"{name}_first{k}t_with") is not None]
                    row[f"{name}_first{k}t_with_share"] = (len(vals), round(sum(vals) / len(vals), 3)) if vals else None
                for h in HORIZONS:
                    vals = [r[f"{name}_d{h}_oriented"] for r in sub if r.get(f"{name}_d{h}_oriented") is not None]
                    if vals:
                        cnt = Counter("up" if v > 0 else "down" if v < 0 else "flat" for v in vals)
                        row[f"{name}_d{h}_oriented"] = dict(n=len(vals), median=median(vals), with_=cnt["up"], flat=cnt["flat"], against=cnt["down"])
            tab[g] = row
        summary[group_key] = tab
    summary["note"] = ("Anchors: plus60 = t0+60 (earliest the A state exists); known = max(t0+60, archived recognition second). "
                       "with = move in the burst polarity direction (continuation); against = reversal. First-excursion shares are over events "
                       "where the excursion occurred before session end. Oriented tick changes are polarity times the signed change from the anchor.")
    (HERE / "a-state-direction-knowable-oct18-summary.json").write_text(json.dumps(summary, indent=2))
    with gzip.open(HERE / "a-state-direction-knowable-oct18-events.jsonl.gz", "wt") as f:
        for r in recs:
            f.write(json.dumps(r) + "\n")
    for gk in ("a_state", "seed"):
        print("==", gk)
        for g, row in summary[gk].items():
            print(g, row["n"])
            for name in ("plus60", "known"):
                print("  ", name, "first with share:", [row.get(f"{name}_first{k}t_with_share") for k in SCALES])
                for h in HORIZONS:
                    d = row.get(f"{name}_d{h}_oriented")
                    if d:
                        print("     d%d: n %d med %s with %d flat %d against %d" % (h, d["n"], d["median"], d["with_"], d["flat"], d["against"]))


if __name__ == "__main__":
    main()
