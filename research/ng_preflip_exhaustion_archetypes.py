"""NG pre-flip -> post-flip exhaustion archetype audit (scratch only).

Hypothesis under test: the dipole curve BEFORE the flip contains information about
how long the dipole will take to exhaust AFTER the flip, independent of whether
price runs up or down.

Research construction:
- price is used ONLY to identify retrospective leg start/duration labels;
- the dipole curve is never multiplied by price/leg direction;
- negative dipole flips are mirrored by the dipole's own polarity at t=0 so the
  same geometry can be compared without cancellation;
- fixed real-time window: -60s .. 0 .. +60s (with -30/+20 summaries too);
- 20s rolling signed trade-volume imbalance, matching the old graph family;
- t=0 is refined within +/-3s of the leg start to the largest absolute dipole
  spike, using dipole only. This is descriptive alignment, not a live trigger.

Outputs include one chop/very-short, one short, and one long archetype plus
independent same-duration matches from other days, and global associations
between pre-flip geometry, post-flip exhaustion, and realized leg duration.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import median

from ng_dipole_runway_audit import load_day, zigzag_legs, mean, quantile, corr, rankdata

THRESH_TICKS = 3
PRE = 60
POST = 60
ROLL = 20
ANCHOR_JITTER = 3
PERSIST = 3
TARGET_Q = {"very_short": 0.10, "short": 0.35, "long": 0.90}


def spearman(x, y):
    pairs = [(float(a), float(b)) for a, b in zip(x, y) if math.isfinite(float(a)) and math.isfinite(float(b))]
    if len(pairs) < 3:
        return float("nan")
    rx = rankdata([a for a, _ in pairs]); ry = rankdata([b for _, b in pairs])
    return corr(rx, ry)


def flow20(day, t):
    lo = max(0, t - ROLL + 1)
    b = sum(day.buy_vol[lo:t + 1]); s = sum(day.sell_vol[lo:t + 1]); z = b + s
    return (b - s) / z if z > 0 else float("nan")


def first_persist_below(post, peak, frac):
    if not (math.isfinite(peak) and peak > 0):
        return None
    lim = frac * peak
    for i in range(1, len(post) - PERSIST + 1):
        w = post[i:i + PERSIST]
        if all(math.isfinite(v) and v <= lim for v in w):
            return i
    return None


def first_zero(post):
    for i, v in enumerate(post[1:], start=1):
        if math.isfinite(v) and v <= 0:
            return i
    return None


def slope(vals, a, b):
    ys = vals[a:b + 1]
    pts = [(i, v) for i, v in enumerate(ys) if math.isfinite(v)]
    if len(pts) < 3:
        return float("nan")
    xs = [p[0] for p in pts]; yy = [p[1] for p in pts]
    mx, my = mean(xs), mean(yy)
    den = sum((x - mx) ** 2 for x in xs)
    return sum((x - mx) * (y - my) for x, y in zip(xs, yy)) / den if den else 0.0


def curvature(vals):
    # Mean second difference over the final 30s before the flip.
    z = vals[-31:]
    d2 = []
    for i in range(1, len(z) - 1):
        if all(math.isfinite(v) for v in (z[i-1], z[i], z[i+1])):
            d2.append(z[i+1] - 2*z[i] + z[i-1])
    return mean(d2) if d2 else float("nan")


def pre_features(pre, peak):
    finite = [v for v in pre if math.isfinite(v)]
    if not finite or not math.isfinite(peak) or peak <= 0:
        return None
    norm = [(v / peak if math.isfinite(v) else float("nan")) for v in pre]
    # Pre is -60..0 inclusive. Segment slopes retain real seconds.
    return {
        "pre60_mean_norm": mean([v for v in norm if math.isfinite(v)]),
        "pre30_mean_norm": mean([v for v in norm[-31:] if math.isfinite(v)]),
        "slope_m60_m30_norm": slope(norm, 0, 30),
        "slope_m30_m10_norm": slope(norm, 30, 50),
        "slope_m10_0_norm": slope(norm, 50, 60),
        "curvature_last30_norm": curvature(norm),
        "area_last30_norm": sum(v for v in norm[-31:] if math.isfinite(v)),
        "level_m60_norm": norm[0],
        "level_m30_norm": norm[30],
        "level_m10_norm": norm[50],
        "level_m5_norm": norm[55],
    }


def shape_vector(pre, peak):
    # Whole left-side shape, amplitude-normalized by the t=0 dipole spike.
    if not math.isfinite(peak) or abs(peak) < 1e-9:
        return None
    v = [(x / peak if math.isfinite(x) else float("nan")) for x in pre]
    if sum(math.isfinite(x) for x in v) < 55:
        return None
    # fill rare gaps linearly by nearest valid values, simple deterministic pass
    out = list(v)
    last = None
    for i in range(len(out)):
        if math.isfinite(out[i]): last = out[i]
        elif last is not None: out[i] = last
    nxt = None
    for i in range(len(out)-1, -1, -1):
        if math.isfinite(out[i]): nxt = out[i]
        elif nxt is not None: out[i] = nxt
    if any(not math.isfinite(x) for x in out): return None
    return out


def pcorr(a, b):
    return corr(a, b)


def event_rows(day):
    out = []
    for leg in zigzag_legs(day.price, THRESH_TICKS):
        s = int(leg["start"]); e = int(leg["end"])
        if s < PRE + ANCHOR_JITTER or s + POST + ANCHOR_JITTER >= 86400:
            continue
        # Flip/spike alignment uses dipole only; no price direction enters orientation.
        cand = []
        for dt in range(-ANCHOR_JITTER, ANCHOR_JITTER + 1):
            v = flow20(day, s + dt)
            if math.isfinite(v): cand.append((abs(v), s + dt, v))
        if not cand: continue
        _, t0, raw0 = max(cand)
        if abs(raw0) < 1e-9: continue
        pol = 1.0 if raw0 > 0 else -1.0
        arc = []
        for dt in range(-PRE, POST + 1):
            v = flow20(day, t0 + dt)
            arc.append(pol * v if math.isfinite(v) else float("nan"))
        pre = arc[:PRE + 1]; post = arc[PRE:]
        peak = post[0]
        feats = pre_features(pre, peak); shp = shape_vector(pre, peak)
        if feats is None or shp is None: continue
        t50 = first_persist_below(post, peak, .50)
        t25 = first_persist_below(post, peak, .25)
        t10 = first_persist_below(post, peak, .10)
        tz = first_zero(post)
        out.append({
            "day": day.day,
            "leg_start_s": s,
            "flip_s": t0,
            "anchor_shift_s": t0 - s,
            "leg_duration_s": int(e - s),
            "leg_ticks": float(leg["ticks"]),
            "dipole_polarity": 1 if raw0 > 0 else -1,
            "peak": float(peak),
            "pre": pre,
            "post": post,
            "pre_shape": shp,
            "features": feats,
            "exh_t50_s": t50,
            "exh_t25_s": t25,
            "exh_t10_s": t10,
            "exh_zero_s": tz,
            "tail20_mean_norm": mean([v/peak for v in post[:21] if math.isfinite(v)]),
            "tail60_mean_norm": mean([v/peak for v in post if math.isfinite(v)]),
            "tail60_area_norm": sum(v/peak for v in post if math.isfinite(v)),
        })
    return out


def json_event(r, include_arc=True):
    d = {k:v for k,v in r.items() if k not in ("pre_shape", "features", "pre", "post")}
    d["features"] = r["features"]
    if include_arc:
        d["pre_m60_to_0"] = r["pre"]
        d["post_0_to_p60"] = r["post"]
    return d


def choose_archetypes(rows):
    ds = [r["leg_duration_s"] for r in rows]
    chosen = {}
    used = set()
    for name, q in TARGET_Q.items():
        target = quantile(ds, q)
        # choose closest duration, then strongest finite spike; no right-side info used
        order = sorted(range(len(rows)), key=lambda i: (abs(rows[i]["leg_duration_s"] - target), -abs(rows[i]["peak"])))
        i = next(i for i in order if i not in used)
        used.add(i); chosen[name] = rows[i]
    return chosen


def duration_matches(rows, archetype, n=4):
    # Match ONLY realized duration and require a different day where possible.
    a = archetype
    pool = [r for r in rows if not (r["day"] == a["day"] and r["flip_s"] == a["flip_s"])]
    pool.sort(key=lambda r: (r["day"] == a["day"], abs(r["leg_duration_s"] - a["leg_duration_s"])))
    got=[]; seen_days=set()
    for r in pool:
        if r["day"] in seen_days: continue
        got.append(r); seen_days.add(r["day"])
        if len(got) == n: return got
    for r in pool:
        if r not in got:
            got.append(r)
            if len(got) == n: break
    return got


def match_summary(a, ms):
    out=[]
    for r in ms:
        out.append({
            "event": json_event(r, include_arc=True),
            "duration_diff_s": r["leg_duration_s"] - a["leg_duration_s"],
            "pre60_shape_corr": pcorr(a["pre_shape"], r["pre_shape"]),
            "post60_shape_corr": pcorr([x/a["peak"] for x in a["post"]], [x/r["peak"] for x in r["post"]]),
            "exh_t25_diff_s": None if a["exh_t25_s"] is None or r["exh_t25_s"] is None else r["exh_t25_s"]-a["exh_t25_s"],
            "exh_zero_diff_s": None if a["exh_zero_s"] is None or r["exh_zero_s"] is None else r["exh_zero_s"]-a["exh_zero_s"],
        })
    return out


def global_summary(rows):
    dur=[r["leg_duration_s"] for r in rows]
    out={"n":len(rows), "duration_quantiles_s":{str(q):quantile(dur,q) for q in (.1,.25,.35,.5,.75,.9)}}
    # Tail metrics; None is censored beyond +60, so report both observed-only and bounded 61s versions.
    for k in ("exh_t50_s","exh_t25_s","exh_t10_s","exh_zero_s"):
        obs=[r for r in rows if r[k] is not None]
        out[k]={
            "observed_fraction":len(obs)/len(rows) if rows else float("nan"),
            "spearman_with_leg_duration_observed":spearman([r[k] for r in obs],[r["leg_duration_s"] for r in obs]) if len(obs)>=3 else float("nan"),
            "spearman_with_leg_duration_censored61":spearman([(r[k] if r[k] is not None else 61) for r in rows],dur),
        }
    out["tail20_mean_norm_spearman_leg_duration"] = spearman([r["tail20_mean_norm"] for r in rows], dur)
    out["tail60_mean_norm_spearman_leg_duration"] = spearman([r["tail60_mean_norm"] for r in rows], dur)
    out["prefeature_spearman_leg_duration"]={k:spearman([r["features"][k] for r in rows],dur) for k in rows[0]["features"]}

    # Direct test of Greg's contention: nearest-neighbor exhaustion prediction from LEFT shape only,
    # forcing neighbors to come from other days. Predict bounded t25 and leg duration.
    pred_ex=[]; true_ex=[]; pred_dur=[]; true_dur=[]; nns=[]
    for r in rows:
        candidates=[q for q in rows if q["day"] != r["day"]]
        sims=sorted(((pcorr(r["pre_shape"],q["pre_shape"]),q) for q in candidates), key=lambda z:z[0], reverse=True)
        nn=[q for _,q in sims[:5]]
        if not nn: continue
        pe=median([(q["exh_t25_s"] if q["exh_t25_s"] is not None else 61) for q in nn])
        pd=median([q["leg_duration_s"] for q in nn])
        pred_ex.append(pe); true_ex.append(r["exh_t25_s"] if r["exh_t25_s"] is not None else 61)
        pred_dur.append(pd); true_dur.append(r["leg_duration_s"])
        nns.append(mean([s for s,_ in sims[:5]]))
    out["left_shape_cross_day_5nn"]={
        "n":len(pred_ex),
        "mean_neighbor_shape_corr":mean(nns),
        "spearman_predicted_vs_actual_t25_exhaustion":spearman(pred_ex,true_ex),
        "spearman_predicted_vs_actual_leg_duration":spearman(pred_dur,true_dur),
        "mae_t25_s":mean([abs(a-b) for a,b in zip(pred_ex,true_ex)]),
        "mae_leg_duration_s":mean([abs(a-b) for a,b in zip(pred_dur,true_dur)]),
    }
    return out


def main(paths):
    days=[load_day(p) for p in paths]
    rows=[]
    for d in days: rows.extend(event_rows(d))
    if len(rows)<20: raise SystemExit(f"too few events: {len(rows)}")
    arcs=choose_archetypes(rows)
    out={
        "definition":{
            "price_direction_used_in_dipole":False,
            "price_use":"retrospective leg start/duration label only",
            "flip_anchor":"largest absolute dipole spike within +/-3s of retrospective leg start",
            "dipole":"20s rolling signed aggressor-volume imbalance; negative flips mirrored by dipole polarity only",
            "window":"fixed -60s .. 0 .. +60s; t=0 is flip/spike",
            "post_exhaustion":"first 3s-persistent fall below 50/25/10% of t0 spike and first zero-cross; no imported crypto threshold chosen as canonical",
            "leg_definition":"3-tick retrospective ZigZag for this archetype pass",
            "archetype_duration_targets":"10th, 35th, 90th percentiles; selection does not use post-flip dipole",
            "match_policy":"closest realized leg durations, preferring different days; then compare dipole curves",
        },
        "global":global_summary(rows),
        "archetypes":{},
    }
    for name,a in arcs.items():
        ms=duration_matches(rows,a,4)
        out["archetypes"][name]={"prototype":json_event(a,True),"matches":match_summary(a,ms)}
    p=Path("ng_preflip_exhaustion_archetypes_results.json")
    p.write_text(json.dumps(out,indent=2,sort_keys=True)+"\n")
    print(json.dumps(out["global"],indent=2,sort_keys=True))
    for name,v in out["archetypes"].items():
        a=v["prototype"]
        print(name, "dur",a["leg_duration_s"],"t25",a["exh_t25_s"],"zero",a["exh_zero_s"],"day",a["day"])
        for m in v["matches"]:
            e=m["event"]
            print("  match",e["day"],e["leg_duration_s"],"precorr",round(m["pre60_shape_corr"],3),"t25",e["exh_t25_s"],"zero",e["exh_zero_s"])
    print("RESULT_FILE="+str(p))

if __name__=="__main__":
    if len(sys.argv)<2: raise SystemExit("pass NG raw day files")
    main(sys.argv[1:])
