"""Test the frozen runway-clock duration math on October 18.

The frozen NG exhaustion runway clock (commit 637778d6, documented in research-atlas-v2/sources/
ng-frozen-runway-clock.md) states reveal totals, in seconds from t0, for the time an exhaustion
lasts at four tick scales: A-fast-collapse 358 / 993 / 1802 / 4386 s and A-persistent
700 / 1802 / 3455 / 6836 s at 3t / 5t / 8t / 13t, with remaining = max(0, total - elapsed). Its
replay proof required persistent > fast-collapse at every scale on each held-out day. Family A is
assigned by a frozen 61-dimensional classifier on the t0..+60 oriented roll-20 curve (not available
here), so this test uses the closest observable proxy already in the frozen contract: persistent =
the oriented curve never reaches zero within +60 (seed P); collapsed = it does (O, S, X). For every
event detected by the frozen detector on the full October 18 session the script measures the first
time after t0 at which the forward-filled last-trade price (and separately the midpoint) has moved
3, 5, 8 and 13 ticks from its t0 value, in either direction and in the polarity direction, with
session-end censoring. It reports medians by family proxy and checks the persistent > collapsed
ordering. It does not refit anything.
"""

import gzip
import json
import sys
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402

SCALES = (3, 5, 8, 13)
FROZEN = {"A-fast-collapse": dict(zip(SCALES, (358, 993, 1802, 4386))), "A-persistent": dict(zip(SCALES, (700, 1802, 3455, 6836)))}


def first_hit(series, t0, k, pol, last, oriented):
    p0 = series[t0]
    if not X.fin(p0):
        return None, True
    for t in range(t0 + 1, last + 1):
        v = series[t]
        if not X.fin(v):
            continue
        d = (v - p0) / X.TICK
        if (pol * d >= k) if oriented else (abs(d) >= k):
            return t - t0, False
    return None, True


def km_median(values, censored_at):
    """Median of a right-censored sample (Kaplan-Meier); values = observed times, censored_at = censoring times."""
    events = sorted([(v, 1) for v in values] + [(c, 0) for c in censored_at])
    n = len(events); at_risk = n; surv = 1.0
    for t, d in events:
        if d:
            surv *= (at_risk - 1) / at_risk
        at_risk -= 1
        if surv <= 0.5:
            return t
    return None


def main():
    stream = X.replay()
    stream["last_trade"] = min(stream["last_trade"], 86399)
    last = stream["last_trade"]
    rows = [json.loads(l) for l in gzip.open(HERE / "exhaustion-clock-oct18-events.jsonl.gz", "rt")]
    rows = [r for r in rows if r["mode"] == "day"]
    out = {}
    per_event = []
    for r in rows:
        rec = dict(t0=r["t0"], seed=r["seed_state"], polarity=r["polarity"], family_proxy="persistent" if r["seed_state"] == "P" else "collapsed")
        for name, series in (("price", stream["price"]), ("mid", stream["mid"])):
            for oriented in (False, True):
                for k in SCALES:
                    t, cens = first_hit(series, r["t0"], k, r["polarity"], last, oriented)
                    rec[f"{name}_{'with' if oriented else 'either'}_{k}t"] = t
                    rec[f"{name}_{'with' if oriented else 'either'}_{k}t_censored"] = cens
                    rec[f"censor_time"] = last - r["t0"]
        per_event.append(rec)
    for name in ("price", "mid"):
        for orient in ("either", "with"):
            table = {}
            for fam in ("persistent", "collapsed"):
                sub = [e for e in per_event if e["family_proxy"] == fam]
                table[fam] = {}
                for k in SCALES:
                    key = f"{name}_{orient}_{k}t"
                    obs = [e[key] for e in sub if e[key] is not None]
                    cens = [e["censor_time"] for e in sub if e[key] is None]
                    table[fam][k] = dict(n=len(sub), observed=len(obs), censored=len(cens),
                                         median_observed_only=median(obs) if obs else None,
                                         km_median=km_median(obs, cens) if obs else None,
                                         q25_observed=X.quantile(obs, .25) if obs else None, q75_observed=X.quantile(obs, .75) if obs else None)
            ordering = {k: (table["persistent"][k]["km_median"] or 0) > (table["collapsed"][k]["km_median"] or 0) for k in SCALES}
            out[f"{name}_{orient}"] = dict(by_family=table, persistent_gt_collapsed_km=ordering)
    # by exact seed state, price either direction
    by_seed = {}
    for st in "POSX":
        sub = [e for e in per_event if e["seed"] == st]
        by_seed[st] = {k: km_median([e[f"price_either_{k}t"] for e in sub if e[f"price_either_{k}t"] is not None], [e["censor_time"] for e in sub if e[f"price_either_{k}t"] is None]) for k in SCALES}
    summary = dict(events=len(per_event), frozen_reveal_totals_s=FROZEN, proxy="persistent = seed P (no zero within +60); collapsed = O/S/X",
                   results=out, km_median_by_seed_price_either=by_seed,
                   note="Times in seconds from t0 to the first forward-filled price at least k ticks from the t0 price; KM medians account for session-end censoring. "
                        "This is a proxy for the frozen Family A split, not the frozen classifier.")
    (HERE / "runway-duration-oct18-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    with gzip.open(HERE / "runway-duration-oct18-events.jsonl.gz", "wt") as f:
        for e in per_event:
            f.write(json.dumps(e) + "\n")
    print(json.dumps(summary, indent=1, default=str))


if __name__ == "__main__":
    main()
