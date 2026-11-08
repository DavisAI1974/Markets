"""What the frozen exhaustion state says besides direction, and what the pre-birth window says, October 18.

Section 12 found the A post-state (fast-collapse / persistent) and the seed state carry no price direction
once knowable (anchored at t0+60). This script asks two further questions on the same 890 frozen-detector
events of the full October 18 session.

1. Beyond direction. From the knowable anchor (t0+60, and max(t0+60, archived recognition)), over the next
   300 and 600 s: price range in ticks, largest absolute excursion from the anchor price, path length,
   path efficiency (|net| / path), 1-second price-change dispersion, print volume (lots), absolute flow
   imbalance, time to the first 1-tick move, share of seconds within one tick of the anchor price, and the
   resting-book imbalance at the anchor. Reported as quartiles by A state, by seed state and by the frozen
   pre-family (A/B/C), with a rank AUC fast-vs-persistent and the same AUC inside pre-event volume terciles
   (activity control).

2. Pre-birth. Over (t0-300, t0] and (t0-60, t0]: volume, oriented price change, range, path length,
   oriented resting-book imbalance at t0-1, the oriented roll-20 pre-arc (base, slope, minimum), prominence,
   gap since the previous event, hour of day. Tested (a) as predictors of the A state (rank AUC), i.e.
   whether the +60 state is already knowable at t0; (b) by Spearman rank correlation against the post-state
   clocks (time to 3 ticks, either and with polarity), the post-anchor 600 s range, and the oriented 300 s
   change from +60 (direction).

3. The frozen pre-family classifier (FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817, SHA
   583f6a12..., loaded through the frozen live-clock module's own integrity-checked loader) is applied to the
   oriented t-60..t0 arc of every event, and the section-12 duration test is repeated on Family A only.

Nothing is refit. The replay is cached in the scratchpad after the first run. No trade cost anywhere.
"""

import gzip
import json
import math
import os
import pickle
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

import numpy as np
from scipy.stats import rankdata, spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402
from runway_duration_test_oct18 import FROZEN, SCALES, first_hit, km_median  # noqa: E402

FROZEN_DIR = Path(os.environ.get("NG_FROZEN_DIR", "/tmp/claude-0/-home-user-Markets/e6cffa19-4561-5119-b5f4-3474c12f9fe5/scratchpad/frozen"))
sys.path.insert(0, str(FROZEN_DIR))
import ng_exhaustion_live_clock as LC  # noqa: E402

PRE_ARTIFACT = FROZEN_DIR / "FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json"
HORIZONS = (300, 600)



def ffill(series, lo, hi):
    """Forward-filled price over [lo, hi], carrying the last finite value before lo; None entries if none yet."""
    out, last = [], None
    for t in range(lo - 1, -1, -1):
        if X.fin(series[t]):
            last = series[t]; break
    for t in range(lo, hi + 1):
        if X.fin(series[t]):
            last = series[t]
        out.append(last)
    return out


def path_metrics(price, cb, cs, a, h, last):
    hi = min(a + h, last)
    if hi <= a:
        return None
    p = ffill(price, a, hi)
    if p[0] is None:
        return None
    arr = np.array(p, dtype=float) / X.TICK
    d = np.diff(arr)
    path = float(np.abs(d).sum())
    net = float(arr[-1] - arr[0])
    moved = np.nonzero(np.abs(arr - arr[0]) >= 1 - 1e-9)[0]
    vol = (cb[hi + 1] - cb[a + 1]) + (cs[hi + 1] - cs[a + 1])
    imb, _ = X.window_imb(cb, cs, hi, hi - a)
    return dict(range=float(arr.max() - arr.min()), max_abs=float(np.abs(arr - arr[0]).max()), path=path,
                efficiency=(abs(net) / path) if path > 0 else None, disp=float(d.std()) if len(d) > 1 else None,
                volume=float(vol), abs_imb=None if imb is None else abs(imb),
                t_first_tick=int(moved[0]) if len(moved) else None, hold_share=float(np.mean(np.abs(arr - arr[0]) < 1 - 1e-9)),
                net=net)


def auc(pos, neg):
    """Rank AUC: probability a persistent value exceeds a fast value (ties count half)."""
    pos = [v for v in pos if v is not None and math.isfinite(v)]
    neg = [v for v in neg if v is not None and math.isfinite(v)]
    if len(pos) < 5 or len(neg) < 5:
        return None
    r = rankdata(pos + neg)
    return round((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)), 3), len(pos), len(neg)


def quart(vals):
    v = sorted(x for x in vals if x is not None and math.isfinite(x))
    if not v:
        return None
    return dict(n=len(v), q25=X.quantile(v, .25), median=median(v), q75=X.quantile(v, .75))


def rho(x, y):
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None and math.isfinite(a) and math.isfinite(b)]
    if len(pairs) < 20:
        return None
    r, p = spearmanr([a for a, _ in pairs], [b for _, b in pairs])
    return dict(rho=round(float(r), 3), p=float(f"{p:.2g}"), n=len(pairs))


def main():
    stream = X.replay_cached()
    last = min(stream["last_trade"], 86399)
    price, mid, flow, bookimb, cb, cs = stream["price"], stream["mid"], stream["roll"], stream["book"], stream["cb"], stream["cs"]
    pre = LC.FrozenPreFamilyClassifier.load(PRE_ARTIFACT)
    cls = {r["t0"]: r for r in (json.loads(l) for l in gzip.open(HERE / f"frozen-a-classifier-{X.TAG}-events.jsonl.gz", "rt"))}
    dur = {r["t0"]: r for r in (json.loads(l) for l in gzip.open(HERE / f"runway-duration-{X.TAG}-events.jsonl.gz", "rt"))}
    ev = [json.loads(l) for l in gzip.open(HERE / f"exhaustion-clock-{X.TAG}-events.jsonl.gz", "rt")]
    ev = [r for r in ev if r["mode"] == "day"]
    recs = []
    for r in ev:
        t0, pol = r["t0"], r["polarity"]
        rec = dict(t0=t0, polarity=pol, seed=r["seed_state"], a_state=cls[t0]["a_state"], prominence=r["prominence"],
                   peak_abs=r["peak_abs"], prev_gap_s=r["prev_gap_s"], hour_utc=((t0 + X.DAY0) % 86400) // 3600,
                   pre_arc_defined=r["pre_arc_defined"], runway_s=r["runway_s"])
        # frozen pre-family on the oriented t-60..t0 arc (leading undefined samples filled with 0 as in section 11)
        raw_arc = [pol * flow[t0 + d] if X.fin(flow[t0 + d]) else X.NAN for d in range(-60, 1)]
        arc = X.fill_curve(raw_arc) or X.fill_curve([0.0] + raw_arc[1:])
        try:
            fc = pre.classify(arc)
            rec["pre_family"], rec["pre_family_dists"] = fc.family, [round(d, 4) for d in fc.distances]
        except LC.LiveClockInputError as exc:
            rec["pre_family"], rec["pre_family_dists"] = "UNAVAILABLE", str(exc)
        # pre-birth features
        for w in (300, 60):
            lo = max(0, t0 - w)
            p = ffill(price, lo, t0)
            if p[0] is not None and p[-1] is not None:
                arr = np.array(p, dtype=float) / X.TICK
                rec[f"pre{w}_oriented_change"] = float(pol * (arr[-1] - arr[0]))
                rec[f"pre{w}_range"] = float(arr.max() - arr.min())
                rec[f"pre{w}_path"] = float(np.abs(np.diff(arr)).sum())
            rec[f"pre{w}_volume"] = float((cb[t0 + 1] - cb[lo]) + (cs[t0 + 1] - cs[lo]))
        rec["pre_book_oriented"] = pol * bookimb[t0 - 1] if X.fin(bookimb[t0 - 1]) else None
        rec["pre_book_abs"] = abs(bookimb[t0 - 1]) if X.fin(bookimb[t0 - 1]) else None
        rec["arc_base10"] = float(np.mean(arc[:10]))
        rec["arc_min"] = float(min(arc))
        rec["arc_slope"] = float(np.polyfit(np.arange(61), arc, 1)[0])
        rec["arc_t0"] = float(arc[-1])
        # knowable anchors
        anchors = {"plus60": t0 + 60}
        if r.get("archived_recognition_s") is not None:
            anchors["known"] = max(t0 + 60, int(r["archived_recognition_s"]))
        for name, a in anchors.items():
            if a > last:
                continue
            rec[f"{name}_book_abs"] = abs(bookimb[a]) if X.fin(bookimb[a]) else None
            for h in HORIZONS:
                m = path_metrics(price, cb, cs, a, h, last)
                if m:
                    for k, v in m.items():
                        rec[f"{name}_{h}_{k}"] = v
                    rec[f"{name}_{h}_oriented_net"] = pol * m["net"]
        d = dur[t0]
        for k in SCALES:
            rec[f"price_with_{k}t"], rec[f"price_either_{k}t"] = d[f"price_with_{k}t"], d[f"price_either_{k}t"]
        rec["censor_time"] = d["censor_time"]
        recs.append(rec)

    summary = dict(events=len(recs), pre_family_sha256=pre.artifact_sha256)
    summary["pre_family_counts"] = dict(Counter(r["pre_family"] for r in recs))
    summary["pre_family_x_a_state"] = dict(Counter(f"{r['pre_family']}|{r['a_state']}" for r in recs))
    summary["pre_family_x_seed"] = dict(Counter(f"{r['pre_family']}|{r['seed']}" for r in recs))

    # 1. beyond direction
    metric_keys = [k for k in recs[0] if k.startswith("plus60_") and not k.endswith("_net")]
    metric_keys = sorted({k for r in recs for k in r if (k.startswith("plus60_") or k.startswith("known_")) and not k.endswith("_net")})
    beyond = {}
    for group_key in ("a_state", "seed", "pre_family"):
        tab = {}
        for g in sorted({r[group_key] for r in recs}):
            sub = [r for r in recs if r[group_key] == g]
            tab[g] = {k: quart([r.get(k) for r in sub]) for k in metric_keys}
            tab[g]["n"] = len(sub)
        beyond[group_key] = tab
    fast = [r for r in recs if r["a_state"] == "A-fast-collapse"]
    pers = [r for r in recs if r["a_state"] == "A-persistent"]
    beyond["auc_persistent_vs_fast"] = {k: auc([r.get(k) for r in pers], [r.get(k) for r in fast]) for k in metric_keys}
    vols = sorted(r["pre300_volume"] for r in recs)
    cuts = (X.quantile(vols, 1 / 3), X.quantile(vols, 2 / 3))
    def terc(v):
        return "low" if v <= cuts[0] else "mid" if v <= cuts[1] else "high"
    strat = {}
    for t in ("low", "mid", "high"):
        f = [r for r in fast if terc(r["pre300_volume"]) == t]
        p = [r for r in pers if terc(r["pre300_volume"]) == t]
        strat[t] = dict(n_fast=len(f), n_persistent=len(p),
                        auc={k: auc([r.get(k) for r in p], [r.get(k) for r in f]) for k in metric_keys if k.startswith("plus60_")})
    beyond["auc_by_pre300_volume_tercile"] = dict(cuts=cuts, strata=strat)
    # same within pre-family A only
    fa = [r for r in fast if r["pre_family"] == "A"]
    pa = [r for r in pers if r["pre_family"] == "A"]
    beyond["auc_persistent_vs_fast_prefamily_A"] = dict(n_fast=len(fa), n_persistent=len(pa),
                                                        auc={k: auc([r.get(k) for r in pa], [r.get(k) for r in fa]) for k in metric_keys if k.startswith("plus60_")})
    summary["beyond_direction"] = beyond

    # 2. pre-birth
    pre_keys = ["pre300_volume", "pre300_oriented_change", "pre300_range", "pre300_path", "pre60_volume", "pre60_oriented_change",
                "pre60_range", "pre60_path", "pre_book_oriented", "pre_book_abs", "arc_base10", "arc_min", "arc_slope", "arc_t0",
                "prominence", "peak_abs", "prev_gap_s", "hour_utc", "runway_s"]
    prebirth = {"quartiles_by_a_state": {}, "auc_a_state_persistent_vs_fast": {}, "spearman": {}}
    for g, sub in (("A-fast-collapse", fast), ("A-persistent", pers)):
        prebirth["quartiles_by_a_state"][g] = {k: quart([r.get(k) for r in sub]) for k in pre_keys}
    prebirth["auc_a_state_persistent_vs_fast"] = {k: auc([r.get(k) for r in pers], [r.get(k) for r in fast]) for k in pre_keys}
    targets = {"time_to_3t_either": "price_either_3t", "time_to_3t_with": "price_with_3t", "range_600_from_plus60": "plus60_600_range",
               "oriented_net_300_from_plus60": "plus60_300_oriented_net", "volume_300_from_plus60": "plus60_300_volume"}
    for tname, tkey in targets.items():
        prebirth["spearman"][tname] = {k: rho([r.get(k) for r in recs], [r.get(tkey) for r in recs]) for k in pre_keys}
    # pre-birth by pre-family
    prebirth["quartiles_by_pre_family"] = {}
    for g in sorted({r["pre_family"] for r in recs}):
        sub = [r for r in recs if r["pre_family"] == g]
        prebirth["quartiles_by_pre_family"][g] = {k: quart([r.get(k) for r in sub]) for k in pre_keys}
        prebirth["quartiles_by_pre_family"][g]["n"] = len(sub)
    # post outcomes by pre-family (direction and clocks), knowable at t0 (pre-family is a t<=0 object)
    post_by_family = {}
    for g in sorted({r["pre_family"] for r in recs}):
        sub = [r for r in recs if r["pre_family"] == g]
        v = [r.get("plus60_300_oriented_net") for r in sub if r.get("plus60_300_oriented_net") is not None]
        post_by_family[g] = dict(n=len(sub), oriented_net_300_from_plus60=dict(n=len(v), with_=sum(1 for x in v if x > 0), flat=sum(1 for x in v if x == 0), against=sum(1 for x in v if x < 0), median=median(v) if v else None),
                                 time_to_3t_either=quart([r.get("price_either_3t") for r in sub]), time_to_3t_with=quart([r.get("price_with_3t") for r in sub]),
                                 range_600_from_plus60=quart([r.get("plus60_600_range") for r in sub]))
    prebirth["post_outcomes_by_pre_family"] = post_by_family
    summary["prebirth"] = prebirth

    # 3. duration test restricted to pre-family A
    fam_a = {}
    for st, sub in (("A-fast-collapse", fa), ("A-persistent", pa)):
        row = {}
        for k in SCALES:
            obs = [r[f"price_with_{k}t"] for r in sub if r[f"price_with_{k}t"] is not None]
            cen = [r["censor_time"] for r in sub if r[f"price_with_{k}t"] is None]
            obs_e = [r[f"price_either_{k}t"] for r in sub if r[f"price_either_{k}t"] is not None]
            cen_e = [r["censor_time"] for r in sub if r[f"price_either_{k}t"] is None]
            row[str(k)] = dict(n=len(sub), km_with=km_median(obs, cen), km_either=km_median(obs_e, cen_e), frozen_total=FROZEN[st][k])
        fam_a[st] = row
    fam_a["persistent_gt_fast_with"] = {str(k): (fam_a["A-persistent"][str(k)]["km_with"] or 0) > (fam_a["A-fast-collapse"][str(k)]["km_with"] or 0) for k in SCALES}
    summary["duration_prefamily_A_only"] = fam_a

    (HERE / f"beyond-direction-prebirth-{X.TAG}-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"beyond-direction-prebirth-{X.TAG}-events.jsonl.gz", "wt") as f:
        for r in recs:
            f.write(json.dumps(r, default=str) + "\n")

    print("pre_family", summary["pre_family_counts"])
    print("pre_family x a_state", summary["pre_family_x_a_state"])
    print("pre_family x seed", summary["pre_family_x_seed"])
    print("\n== beyond direction: AUC persistent vs fast (plus60)")
    for k, v in beyond["auc_persistent_vs_fast"].items():
        if k.startswith("plus60_"):
            print(f"  {k:32s} {v}")
    print("\n== quartiles by a_state (plus60_300 / plus60_600)")
    for g, tab in beyond["a_state"].items():
        print(g, tab["n"])
        for k in metric_keys:
            if k.startswith("plus60_"):
                print(f"   {k:30s} {tab[k]}")
    print("\n== AUC by pre300 volume tercile", cuts)
    for t, s in strat.items():
        print(t, s["n_fast"], s["n_persistent"])
        for k, v in s["auc"].items():
            if k.startswith("plus60_600") or k == "plus60_book_abs":
                print(f"   {k:30s} {v}")
    print("\n== pre-family A only AUC", beyond["auc_persistent_vs_fast_prefamily_A"]["n_fast"], beyond["auc_persistent_vs_fast_prefamily_A"]["n_persistent"])
    for k, v in beyond["auc_persistent_vs_fast_prefamily_A"]["auc"].items():
        if k.startswith("plus60_600"):
            print(f"   {k:30s} {v}")
    print("\n== prebirth -> a_state AUC")
    for k, v in prebirth["auc_a_state_persistent_vs_fast"].items():
        print(f"  {k:24s} {v}")
    print("\n== prebirth spearman")
    for t, tab in prebirth["spearman"].items():
        print(t)
        for k, v in tab.items():
            if v and abs(v["rho"]) >= 0.1:
                print(f"   {k:24s} {v}")
    print("\n== post outcomes by pre-family")
    for g, v in post_by_family.items():
        print(g, json.dumps(v))
    print("\n== duration, pre-family A only")
    print(json.dumps(fam_a))


if __name__ == "__main__":
    main()
