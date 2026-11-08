"""What else the frozen exhaustion state might do: the book and the next event, October 18.

Companion to beyond_direction_prebirth_oct18.py. From the knowable anchor t0+60 the script asks, by A state
and by seed state, (1) whether the state says anything about the resting book: spread, 10-level depth on
the side the burst pushes into (toward side: asks for a buy burst) and the side it leaves (away side), best
quote sizes, and their change from +60 to +360 and +660; (2) whether it says anything about the next
frozen-detector event: the gap to its t0, whether its polarity flips, and its seed and A state (transition
tables); (3) the burst's own book response from t0 to +60 (contemporaneous, flagged as such). Rank AUC
persistent-vs-fast on every measure, repeated inside pre-event volume terciles as the activity control.
Nothing refit, no trade cost.
"""

import gzip
import json
import math
import sys
from collections import Counter
from pathlib import Path
from statistics import median

import numpy as np
from scipy.stats import rankdata

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import exhaustion_clock_reanalysis_oct18 as X  # noqa: E402


def auc(pos, neg):
    pos = [v for v in pos if v is not None and math.isfinite(v)]
    neg = [v for v in neg if v is not None and math.isfinite(v)]
    if len(pos) < 5 or len(neg) < 5:
        return None
    r = rankdata(pos + neg)
    return round(float((r[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))), 3), len(pos), len(neg)


def quart(vals):
    v = sorted(x for x in vals if x is not None and math.isfinite(x))
    return dict(n=len(v), q25=X.quantile(v, .25), median=median(v), q75=X.quantile(v, .75)) if v else None


def val(series, t):
    return series[t] if 0 <= t < len(series) and X.fin(series[t]) else None


def main():
    stream = X.replay_cached()
    last = min(stream["last_trade"], 86399)
    spread, bdep, adep, btch, atch, cb, cs, price = (stream[k] for k in ("spread", "bid_depth", "ask_depth", "bid_touch", "ask_touch", "cb", "cs", "price"))
    cls = {r["t0"]: r for r in (json.loads(l) for l in gzip.open(HERE / f"frozen-a-classifier-{X.TAG}-events.jsonl.gz", "rt"))}
    ev = [json.loads(l) for l in gzip.open(HERE / f"exhaustion-clock-{X.TAG}-events.jsonl.gz", "rt")]
    ev = sorted((r for r in ev if r["mode"] == "day"), key=lambda r: r["t0"])
    recs = []
    for i, r in enumerate(ev):
        t0, pol = r["t0"], r["polarity"]
        a = t0 + 60
        rec = dict(t0=t0, polarity=pol, seed=r["seed_state"], a_state=cls[t0]["a_state"], pre300_volume=(cb[t0 + 1] - cb[max(0, t0 - 299)]) + (cs[t0 + 1] - cs[max(0, t0 - 299)]))
        toward, away = (adep, bdep) if pol > 0 else (bdep, adep)          # buy burst pushes into asks
        toward_t, away_t = (atch, btch) if pol > 0 else (btch, atch)
        # contemporaneous: t0 -> +60
        for name, ser in (("spread", spread), ("toward_depth", toward), ("away_depth", away), ("toward_touch", toward_t), ("away_touch", away_t)):
            v0, v60 = val(ser, t0), val(ser, a)
            rec[f"t0_{name}"] = v0
            rec[f"plus60_{name}"] = v60
            if v0 is not None and v60 is not None:
                rec[f"t0_to_60_{name}_change"] = v60 - v0
                rec[f"t0_to_60_{name}_ratio"] = (v60 / v0) if v0 else None
            for h in (300, 600):
                vh = val(ser, a + h) if a + h <= last else None
                if v60 is not None and vh is not None:
                    rec[f"plus60_{h}_{name}_change"] = vh - v60
                    rec[f"plus60_{h}_{name}_ratio"] = (vh / v60) if v60 else None
        if val(toward, a) is not None and val(away, a) is not None and (val(toward, a) + val(away, a)) > 0:
            rec["plus60_toward_share"] = val(toward, a) / (val(toward, a) + val(away, a))
        # next event
        if i + 1 < len(ev):
            nx = ev[i + 1]
            rec["next_gap_s"] = nx["t0"] - t0
            rec["next_gap_from_plus60_s"] = nx["t0"] - a
            rec["next_flip"] = int(nx["polarity"] != pol)
            rec["next_seed"] = nx["seed_state"]
            rec["next_a_state"] = cls[nx["t0"]]["a_state"]
            rec["next_before_plus60"] = int(nx["t0"] <= a)
        recs.append(rec)
    fast = [r for r in recs if r["a_state"] == "A-fast-collapse"]
    pers = [r for r in recs if r["a_state"] == "A-persistent"]
    num_keys = sorted(k for k in set().union(*(r.keys() for r in recs)) if k not in ("t0", "polarity", "seed", "a_state", "next_seed", "next_a_state") and any(isinstance(r.get(k), (int, float)) for r in recs))
    summary = dict(events=len(recs))
    summary["quartiles_by_a_state"] = {g: {k: quart([r.get(k) for r in sub]) for k in num_keys} for g, sub in (("A-fast-collapse", fast), ("A-persistent", pers))}
    summary["quartiles_by_seed"] = {g: {k: quart([r.get(k) for r in recs if r["seed"] == g]) for k in num_keys} for g in "PSOX"}
    summary["auc_persistent_vs_fast"] = {k: auc([r.get(k) for r in pers], [r.get(k) for r in fast]) for k in num_keys}
    vols = sorted(r["pre300_volume"] for r in recs)
    cuts = (X.quantile(vols, 1 / 3), X.quantile(vols, 2 / 3))
    terc = lambda v: "low" if v <= cuts[0] else "mid" if v <= cuts[1] else "high"
    summary["auc_by_pre300_volume_tercile"] = {t: dict(n_fast=sum(1 for r in fast if terc(r["pre300_volume"]) == t), n_persistent=sum(1 for r in pers if terc(r["pre300_volume"]) == t),
                                                      auc={k: auc([r.get(k) for r in pers if terc(r["pre300_volume"]) == t], [r.get(k) for r in fast if terc(r["pre300_volume"]) == t]) for k in num_keys})
                                               for t in ("low", "mid", "high")}
    # transitions
    tr = {}
    for key in ("a_state", "seed"):
        nk = "next_" + key
        tab = Counter((r[key], r[nk]) for r in recs if r.get(nk))
        tr[key] = {f"{a}->{b}": n for (a, b), n in sorted(tab.items())}
        rows = {}
        for g in sorted({r[key] for r in recs}):
            sub = [r for r in recs if r[key] == g and r.get(nk)]
            rows[g] = dict(n=len(sub), next_flip_share=round(sum(r["next_flip"] for r in sub) / len(sub), 3) if sub else None,
                           next_gap_s=quart([r["next_gap_s"] for r in sub]), next_before_plus60_share=round(sum(r["next_before_plus60"] for r in sub) / len(sub), 3) if sub else None,
                           next_dist=dict(Counter(r[nk] for r in sub)))
        tr[key + "_rows"] = rows
    base_flip = round(sum(r["next_flip"] for r in recs if "next_flip" in r) / sum(1 for r in recs if "next_flip" in r), 3)
    tr["base_next_flip_share"] = base_flip
    summary["transitions"] = tr
    summary["note"] = ("toward side = the book side the burst pushes into (asks for a buy burst); away side = the side it leaves. "
                       "t0_to_60 measures are contemporaneous with the state definition and are not knowable at t0. "
                       "plus60_* measures are knowable at the anchor; plus60_{h}_* changes are the test of what the state says about the book after it is known.")
    (HERE / f"other-things-{X.TAG}-summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    with gzip.open(HERE / f"other-things-{X.TAG}-events.jsonl.gz", "wt") as f:
        for r in recs:
            f.write(json.dumps(r, default=str) + "\n")
    print("== AUC persistent vs fast")
    for k, v in summary["auc_persistent_vs_fast"].items():
        print(f"  {k:36s} {v}")
    print("\n== medians fast | persistent")
    for k in num_keys:
        a_, b_ = summary["quartiles_by_a_state"]["A-fast-collapse"][k], summary["quartiles_by_a_state"]["A-persistent"][k]
        print(f"  {k:36s} {a_ and a_['median']} | {b_ and b_['median']}")
    print("\n== AUC by tercile (plus60_* and next_*)")
    for t, s in summary["auc_by_pre300_volume_tercile"].items():
        print(t, s["n_fast"], s["n_persistent"])
        for k, v in s["auc"].items():
            if k.startswith("plus60_") or k.startswith("next_"):
                print(f"   {k:34s} {v}")
    print("\n== transitions")
    print(json.dumps(tr, indent=1))


if __name__ == "__main__":
    main()
