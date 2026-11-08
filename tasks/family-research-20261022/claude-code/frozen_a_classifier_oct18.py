"""Apply the frozen Family A post-state classifier (FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816,
SHA-256 698b956f...) to every exhaustion event the frozen detector finds on the full October 18 session,
then repeat the 3/5/8/13-tick duration test by the exact A state instead of the P/collapsed proxy.

The classifier contract (from the artifact): 61 oriented roll-20 samples at t0..+60, each divided by the
t0 value, nearest of two Euclidean centroids; raw cluster 0 = A-fast-collapse, 1 = A-persistent. It was fit
on revealed Family A events only (n 1,619); the frozen reveal counts were 831 fast-collapse and 785
persistent on four held-out days. The pre-family A/B/C assignment uses a separate frozen scaler and
centroids on t-60..t0 geometry that is not carried in this repository, so here the A classifier is applied
to all events (and to the P/collapsed proxy halves) and that is stated. Nothing is refit; the artifact is
read from the pinned commit 637778d6 and its hash is checked.
"""

import gzip
import hashlib
import json
import math
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402
from runway_duration_test_oct18 import FROZEN, SCALES, first_hit, km_median  # noqa: E402

COMMIT = "637778d6f460940379ac0feaf8223be47971c11f"
ARTIFACT = "research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json"
SHA = "698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9"


def main():
    raw = subprocess.check_output(["git", "show", f"{COMMIT}:{ARTIFACT}"])
    if hashlib.sha256(raw).hexdigest() != SHA:
        raise SystemExit("classifier hash drift")
    art = json.loads(raw)
    cents = [tuple(float(x) for x in c) for c in art["centroids_raw_cluster_order"]]
    labels = {0: "A-fast-collapse", 1: "A-persistent"}
    stream = X.replay_cached()
    stream["last_trade"] = min(stream["last_trade"], 86399)
    last = stream["last_trade"]
    flow = stream["roll"]
    rows = [json.loads(l) for l in gzip.open(HERE / f"exhaustion-clock-{X.TAG}-events.jsonl.gz", "rt")]
    rows = [r for r in rows if r["mode"] == "day"]
    out = []
    for r in rows:
        t0, pol = r["t0"], r["polarity"]
        raw_arc = [pol * flow[t0 + d] if X.fin(flow[t0 + d]) else X.NAN for d in range(-60, 61)]
        arc = X.fill_curve(raw_arc) or X.fill_curve([0.0] + raw_arc[1:])
        post = arc[60:]
        if post[0] == 0 or not all(math.isfinite(v) for v in post):
            state, dists = "A_STATE_UNAVAILABLE", None
        else:
            norm = [v / post[0] for v in post]
            dists = [math.dist(norm, c) for c in cents]
            state = labels[0] if dists[0] <= dists[1] else labels[1]
        rec = dict(t0=t0, polarity=pol, seed=r["seed_state"], proxy="persistent" if r["seed_state"] == "P" else "collapsed",
                   a_state=state, dist_fast=None if dists is None else dists[0], dist_persistent=None if dists is None else dists[1],
                   censor_time=last - t0)
        for name, series in (("price", stream["price"]), ("mid", stream["mid"])):
            for oriented in (False, True):
                for k in SCALES:
                    t, _ = first_hit(series, t0, k, pol, last, oriented)
                    rec[f"{name}_{'with' if oriented else 'either'}_{k}t"] = t
        out.append(rec)
    states = Counter(e["a_state"] for e in out)
    cross = Counter((e["proxy"], e["a_state"]) for e in out)
    results = {}
    for name in ("price", "mid"):
        for orient in ("either", "with"):
            tab = {}
            for st in ("A-fast-collapse", "A-persistent"):
                sub = [e for e in out if e["a_state"] == st]
                tab[st] = {}
                for k in SCALES:
                    key = f"{name}_{orient}_{k}t"
                    obs = [e[key] for e in sub if e[key] is not None]
                    cens = [e["censor_time"] for e in sub if e[key] is None]
                    tab[st][k] = dict(n=len(sub), observed=len(obs), censored=len(cens), km_median=km_median(obs, cens) if obs else None,
                                      q25=X.quantile(obs, .25) if obs else None, q75=X.quantile(obs, .75) if obs else None,
                                      frozen_total=FROZEN[st][k])
            results[f"{name}_{orient}"] = dict(by_state=tab, persistent_gt_fast_km={k: (tab["A-persistent"][k]["km_median"] or 0) > (tab["A-fast-collapse"][k]["km_median"] or 0) for k in SCALES})
    # the frozen countdown rule evaluated at the state-legal gate (+60 s): remaining = total - 60; compare with the realised remaining time to each scale
    countdown = {}
    for st in ("A-fast-collapse", "A-persistent"):
        sub = [e for e in out if e["a_state"] == st]
        countdown[st] = {}
        for k in SCALES:
            key = f"price_with_{k}t"
            realised = [e[key] - 60 for e in sub if e[key] is not None and e[key] > 60]
            already = sum(1 for e in sub if e[key] is not None and e[key] <= 60)
            cens = [e["censor_time"] - 60 for e in sub if e[key] is None]
            countdown[st][k] = dict(frozen_remaining_at_plus60=FROZEN[st][k] - 60, realised_km_median_remaining=km_median(realised, cens) if realised else None,
                                    reached_before_plus60=already, n=len(sub))
    summary = dict(events=len(out), classifier_sha256=SHA, commit=COMMIT, a_state_counts=states,
                   proxy_vs_a_state={f"{p}|{s}": n for (p, s), n in cross.items()},
                   frozen_reveal_counts=dict(fast=831, persistent=785), results=results, countdown_check=countdown,
                   note="A classifier applied to all detected events, not only frozen Family A; the pre-family A/B/C artifact is not in this repository. Times are seconds from t0 to the first forward-filled price k ticks away; KM medians handle session-end censoring.")
    (HERE / f"frozen-a-classifier-{X.TAG}-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"frozen-a-classifier-{X.TAG}-events.jsonl.gz", "wt") as f:
        for e in out:
            f.write(json.dumps(e) + "\n")
    print(json.dumps(dict(events=len(out), a_state_counts=states, proxy_vs_a_state=summary["proxy_vs_a_state"]), indent=1, default=str))
    for key in ("price_with", "price_either", "mid_with"):
        r = results[key]
        print("==", key, "persistent > fast (KM):", r["persistent_gt_fast_km"])
        for st in ("A-fast-collapse", "A-persistent"):
            print("  ", st, {k: (v["km_median"], v["frozen_total"], f"obs {v['observed']} cens {v['censored']}") for k, v in r["by_state"][st].items()})
    print("== countdown at +60 (frozen remaining vs realised KM remaining, price with polarity)")
    for st, d in countdown.items():
        print("  ", st, {k: (v["frozen_remaining_at_plus60"], v["realised_km_median_remaining"], f"reached<=60: {v['reached_before_plus60']}") for k, v in d.items()})


if __name__ == "__main__":
    main()
