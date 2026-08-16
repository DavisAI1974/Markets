"""NG-native dipole shape-family audit (scratch research only).

Goal
----
Discover NG's own pre-flip dipole geometry and test whether *similar NG pre-flip
curves* reproduce similar post-flip exhaustion durations, without assuming the
crypto hockey-stick/ramp vocabulary transfers to NG.

Critical construction rules
---------------------------
1. t=0 is detected from the DIPOLE ONLY. Price is never used to find or orient
   the dipole event.
2. Negative dipole spikes are mirrored by the dipole's own polarity at t=0 so
   opposite polarities can share one geometry vocabulary.
3. Fixed real-time windows: -60s .. 0 .. +60s. No duration normalization.
4. Post-flip exhaustion is an OUTCOME only.
5. Price legs are attached only AFTER dipole events are frozen, as external
   structural labels. Price direction is irrelevant to dipole geometry.
6. Cross-day matching is the primary validation. Similarity is measured only
   from the pre-flip dipole curve.

We run two NG-native smoothing windows (20s, 60s) because NG trade sparsity can
make one window too jagged/saturated. Neither window is chosen from outcomes.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import median

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ng_dipole_runway_audit import load_day, zigzag_legs, mean, quantile, corr

PRE = 60
POST = 60
ROLLS = (20, 60)
PEAK_Q = 0.85
LOCAL_RADIUS = 5
REFRACTORY = 45
PERSIST = 3
PRICE_THRESH_TICKS = (3, 5)
TOPK = 5


def rankdata(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    k = 0
    while k < len(order):
        j = k + 1
        while j < len(order) and xs[order[j]] == xs[order[k]]:
            j += 1
        v = 0.5 * (k + j - 1) + 1.0
        for p in range(k, j):
            r[order[p]] = v
        k = j
    return r


def spearman(x, y):
    pairs = [(float(a), float(b)) for a, b in zip(x, y)
             if math.isfinite(float(a)) and math.isfinite(float(b))]
    if len(pairs) < 3:
        return float("nan")
    return corr(rankdata([a for a, _ in pairs]), rankdata([b for _, b in pairs]))


def flow_series(day, roll):
    """Causal trailing signed aggressor-volume imbalance at 1s resolution."""
    n = len(day.buy_vol)
    cb = [0.0] * (n + 1)
    cs = [0.0] * (n + 1)
    for i in range(n):
        cb[i + 1] = cb[i] + day.buy_vol[i]
        cs[i + 1] = cs[i] + day.sell_vol[i]
    out = [float("nan")] * n
    for t in range(n):
        lo = max(0, t - roll + 1)
        b = cb[t + 1] - cb[lo]
        s = cs[t + 1] - cs[lo]
        z = b + s
        if z > 0:
            out[t] = (b - s) / z
    return out


def finite_median(xs):
    a = sorted(float(x) for x in xs if math.isfinite(float(x)))
    return median(a) if a else float("nan")


def detect_dipole_peaks(flow):
    """Outcome-free dipole spike detector.

    Candidate must be a local |flow| maximum over +/-5s and exceed the day's
    85th percentile of |flow|. We rank candidates by a pre-only prominence:
    |t0| minus the median |flow| over t0-30..t0-10. Refractory selection keeps
    the strongest pre-prominent spike in each 45s neighborhood.
    """
    mags = [abs(v) for v in flow if math.isfinite(v)]
    if not mags:
        return []
    thr = quantile(mags, PEAK_Q)
    cand = []
    for t in range(PRE, len(flow) - POST):
        v = flow[t]
        if not math.isfinite(v) or abs(v) < thr:
            continue
        local = [abs(flow[j]) for j in range(t - LOCAL_RADIUS, t + LOCAL_RADIUS + 1)
                 if math.isfinite(flow[j])]
        if not local or abs(v) < max(local) - 1e-12:
            continue
        base = finite_median(abs(flow[j]) for j in range(max(0, t - 30), max(0, t - 9))
                             if math.isfinite(flow[j]))
        if not math.isfinite(base):
            base = 0.0
        prom = abs(v) - base
        cand.append((t, abs(v), prom))

    # Greedy pre-only prominence selection, then chronological order.
    cand.sort(key=lambda z: (z[2], z[1]), reverse=True)
    picked = []
    for row in cand:
        t = row[0]
        if any(abs(t - p[0]) < REFRACTORY for p in picked):
            continue
        picked.append(row)
    picked.sort(key=lambda z: z[0])
    return picked


def fill_curve(vals):
    out = list(vals)
    last = None
    for i, v in enumerate(out):
        if math.isfinite(v):
            last = v
        elif last is not None:
            out[i] = last
    nxt = None
    for i in range(len(out) - 1, -1, -1):
        if math.isfinite(out[i]):
            nxt = out[i]
        elif nxt is not None:
            out[i] = nxt
    if any(not math.isfinite(v) for v in out):
        return None
    return out


def first_persist_below(post, peak, frac):
    lim = frac * peak
    for i in range(1, len(post) - PERSIST + 1):
        if all(math.isfinite(v) and v <= lim for v in post[i:i + PERSIST]):
            return i
    return None


def first_zero(post):
    for i in range(1, len(post) - PERSIST + 1):
        if all(math.isfinite(v) and v <= 0 for v in post[i:i + PERSIST]):
            return i
    return None


def curve_corr(a, b):
    return corr(a, b)


def build_price_labels(day):
    return {th: zigzag_legs(day.price, th) for th in PRICE_THRESH_TICKS}


def containing_leg(legs, t):
    for leg in legs:
        if leg["start"] <= t <= leg["end"]:
            return leg
    return None


def nearest_start_leg(legs, t, max_gap=15):
    if not legs:
        return None
    leg = min(legs, key=lambda z: abs(z["start"] - t))
    return leg if abs(leg["start"] - t) <= max_gap else None


def event_rows(day, roll):
    flow = flow_series(day, roll)
    labels = build_price_labels(day)
    rows = []
    for t0, mag, prom in detect_dipole_peaks(flow):
        raw0 = flow[t0]
        if not math.isfinite(raw0) or abs(raw0) < 1e-9:
            continue
        pol = 1.0 if raw0 > 0 else -1.0
        raw_arc = [flow[t0 + dt] for dt in range(-PRE, POST + 1)]
        arc = [pol * v if math.isfinite(v) else float("nan") for v in raw_arc]
        filled = fill_curve(arc)
        if filled is None:
            continue
        pre = filled[:PRE + 1]
        post = filled[PRE:]
        peak = pre[-1]
        if peak <= 0:
            continue

        # Relative shape preserves geometry; raw oriented curve preserves height.
        rel = [v / peak for v in pre]
        base10 = mean(pre[:10])
        excursion = peak - base10
        if abs(excursion) > 1e-9:
            build = [(v - base10) / excursion for v in pre]
        else:
            build = [0.0 for _ in pre]

        row = {
            "day": day.day,
            "roll_s": roll,
            "flip_s": t0,
            "dipole_polarity": 1 if raw0 > 0 else -1,
            "peak_abs": abs(raw0),
            "pre_prominence": prom,
            "pre_base10": base10,
            "pre_excursion": excursion,
            "pre_raw": pre,
            "pre_rel": rel,
            "pre_build": build,
            "post_raw": post,
            "exh_t50_s": first_persist_below(post, peak, .50),
            "exh_t25_s": first_persist_below(post, peak, .25),
            "exh_t10_s": first_persist_below(post, peak, .10),
            "exh_zero_s": first_zero(post),
        }
        for th in PRICE_THRESH_TICKS:
            cl = containing_leg(labels[th], t0)
            nl = nearest_start_leg(labels[th], t0)
            row[f"price_{th}t_containing_duration_s"] = None if cl is None else cl["duration"]
            row[f"price_{th}t_containing_remaining_s"] = None if cl is None else max(0, cl["end"] - t0)
            row[f"price_{th}t_nearstart_duration_s"] = None if nl is None else nl["duration"]
            row[f"price_{th}t_nearstart_gap_s"] = None if nl is None else nl["start"] - t0
        rows.append(row)
    return rows


def amplitude_similarity(a, b):
    """0..1 symmetric ratio similarity of baseline-to-spike excursion magnitude."""
    x = abs(a["pre_excursion"]); y = abs(b["pre_excursion"])
    if x < 1e-9 and y < 1e-9:
        return 1.0
    if x < 1e-9 or y < 1e-9:
        return 0.0
    return min(x, y) / max(x, y)


def outcome_value(r, key, censored=61):
    v = r.get(key)
    return censored if v is None else float(v)


def pairwise_similarity_summary(rows):
    """Direct test: do more-similar LEFT curves have more-similar RIGHT outcomes?"""
    pairs = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if a["day"] == b["day"]:
                continue
            sim = curve_corr(a["pre_build"], b["pre_build"])
            amp = amplitude_similarity(a, b)
            if not math.isfinite(sim):
                continue
            rec = {
                "shape_corr": sim,
                "amp_similarity": amp,
                "abs_t25_diff": abs(outcome_value(a, "exh_t25_s") - outcome_value(b, "exh_t25_s")),
                "abs_zero_diff": abs(outcome_value(a, "exh_zero_s") - outcome_value(b, "exh_zero_s")),
            }
            for th in PRICE_THRESH_TICKS:
                va = a.get(f"price_{th}t_nearstart_duration_s")
                vb = b.get(f"price_{th}t_nearstart_duration_s")
                rec[f"abs_price_{th}t_dur_diff"] = None if va is None or vb is None else abs(va - vb)
            pairs.append(rec)

    bins = [(-1.01, 0.0), (0.0, .3), (.3, .6), (.6, .8), (.8, .9), (.9, .95), (.95, 1.01)]
    out_bins = {}
    for lo, hi in bins:
        p = [z for z in pairs if lo < z["shape_corr"] <= hi]
        if not p:
            continue
        key = f"({lo:.2f},{hi:.2f}]"
        d = {
            "n_pairs": len(p),
            "shape_corr_mean": mean([z["shape_corr"] for z in p]),
            "amp_similarity_mean": mean([z["amp_similarity"] for z in p]),
            "median_abs_t25_diff_s": median([z["abs_t25_diff"] for z in p]),
            "median_abs_zero_diff_s": median([z["abs_zero_diff"] for z in p]),
        }
        for th in PRICE_THRESH_TICKS:
            vals = [z[f"abs_price_{th}t_dur_diff"] for z in p if z[f"abs_price_{th}t_dur_diff"] is not None]
            d[f"median_abs_price_{th}t_duration_diff_s"] = median(vals) if vals else None
            d[f"price_{th}t_pair_n"] = len(vals)
        out_bins[key] = d

    # Strict same-family matches: high curve correlation + similar excursion height.
    strict = [z for z in pairs if z["shape_corr"] >= .90 and z["amp_similarity"] >= .67]
    loose = [z for z in pairs if z["shape_corr"] < .30]
    def pack(p):
        if not p:
            return {"n_pairs": 0}
        d = {
            "n_pairs": len(p),
            "mean_shape_corr": mean([z["shape_corr"] for z in p]),
            "mean_amp_similarity": mean([z["amp_similarity"] for z in p]),
            "median_abs_t25_diff_s": median([z["abs_t25_diff"] for z in p]),
            "median_abs_zero_diff_s": median([z["abs_zero_diff"] for z in p]),
        }
        for th in PRICE_THRESH_TICKS:
            vals = [z[f"abs_price_{th}t_dur_diff"] for z in p if z[f"abs_price_{th}t_dur_diff"] is not None]
            d[f"median_abs_price_{th}t_duration_diff_s"] = median(vals) if vals else None
        return d

    return {
        "cross_day_pairs": len(pairs),
        "similarity_bins": out_bins,
        "strict_same_family_shape_ge_0_90_amp_ge_0_67": pack(strict),
        "dissimilar_shape_lt_0_30": pack(loose),
    }


def cross_day_knn(rows):
    pred25=[]; true25=[]; pred0=[]; true0=[]
    pred3=[]; true3=[]; pred5=[]; true5=[]; sims=[]; amps=[]
    details=[]
    for r in rows:
        cand=[]
        for q in rows:
            if q["day"] == r["day"]:
                continue
            s=curve_corr(r["pre_build"], q["pre_build"])
            if math.isfinite(s):
                cand.append((s, amplitude_similarity(r,q), q))
        cand.sort(key=lambda z:(z[0], z[1]), reverse=True)
        nn=cand[:TOPK]
        if not nn:
            continue
        qs=[q for _,_,q in nn]
        pred25.append(median([outcome_value(q,"exh_t25_s") for q in qs])); true25.append(outcome_value(r,"exh_t25_s"))
        pred0.append(median([outcome_value(q,"exh_zero_s") for q in qs])); true0.append(outcome_value(r,"exh_zero_s"))
        sims.append(mean([s for s,_,_ in nn])); amps.append(mean([a for _,a,_ in nn]))
        for th,pp,tt in ((3,pred3,true3),(5,pred5,true5)):
            vals=[q.get(f"price_{th}t_nearstart_duration_s") for q in qs]
            vals=[v for v in vals if v is not None]
            tv=r.get(f"price_{th}t_nearstart_duration_s")
            if vals and tv is not None:
                pp.append(median(vals)); tt.append(tv)
        if len(details)<12:
            details.append({
                "day":r["day"],"flip_s":r["flip_s"],
                "actual_t25":true25[-1],"pred_t25":pred25[-1],
                "mean_neighbor_shape_corr":sims[-1],"mean_neighbor_amp_similarity":amps[-1],
                "neighbors":[{"day":q["day"],"flip_s":q["flip_s"],"shape_corr":s,"amp_similarity":a,
                              "t25":outcome_value(q,"exh_t25_s"),
                              "price3t":q.get("price_3t_nearstart_duration_s")}
                             for s,a,q in nn]
            })
    return {
        "n":len(pred25),
        "mean_top5_shape_corr":mean(sims) if sims else None,
        "mean_top5_amp_similarity":mean(amps) if amps else None,
        "spearman_pred_vs_actual_t25":spearman(pred25,true25),
        "mae_t25_s":mean([abs(a-b) for a,b in zip(pred25,true25)]) if pred25 else None,
        "spearman_pred_vs_actual_zero":spearman(pred0,true0),
        "mae_zero_s":mean([abs(a-b) for a,b in zip(pred0,true0)]) if pred0 else None,
        "spearman_pred_vs_actual_price3t_duration":spearman(pred3,true3) if len(pred3)>=3 else None,
        "mae_price3t_duration_s":mean([abs(a-b) for a,b in zip(pred3,true3)]) if pred3 else None,
        "spearman_pred_vs_actual_price5t_duration":spearman(pred5,true5) if len(pred5)>=3 else None,
        "mae_price5t_duration_s":mean([abs(a-b) for a,b in zip(pred5,true5)]) if pred5 else None,
        "sample_matches":details,
    }


def choose_exhaustion_archetypes(rows):
    """Descriptive exemplars selected AFTER outcomes solely to visualize short/medium/long exhaustion."""
    vals=[outcome_value(r,"exh_t25_s") for r in rows]
    targets={"very_short":quantile(vals,.10),"short":quantile(vals,.40),"long":quantile(vals,.90)}
    used=set(); out={}
    for name,target in targets.items():
        order=sorted(range(len(rows)), key=lambda i:(abs(outcome_value(rows[i],"exh_t25_s")-target), -rows[i]["pre_prominence"]))
        i=next(i for i in order if i not in used); used.add(i)
        a=rows[i]
        cand=[]
        for q in rows:
            if q["day"]==a["day"]: continue
            s=curve_corr(a["pre_build"],q["pre_build"])
            if math.isfinite(s): cand.append((s,amplitude_similarity(a,q),q))
        cand.sort(key=lambda z:(z[0],z[1]), reverse=True)
        out[name]={"prototype":a,"matches":[{"shape_corr":s,"amp_similarity":am,"event":q} for s,am,q in cand[:5]]}
    return out


def compact_event(r):
    keys=["day","roll_s","flip_s","dipole_polarity","peak_abs","pre_prominence","pre_base10","pre_excursion",
          "exh_t50_s","exh_t25_s","exh_t10_s","exh_zero_s"]
    for th in PRICE_THRESH_TICKS:
        keys += [f"price_{th}t_nearstart_duration_s",f"price_{th}t_nearstart_gap_s",
                 f"price_{th}t_containing_duration_s",f"price_{th}t_containing_remaining_s"]
    d={k:r.get(k) for k in keys}
    d["pre_m60_to_0"]=r["pre_raw"]
    d["post_0_to_p60"]=r["post_raw"]
    return d


def render(roll, archetypes, path):
    fig, axs=plt.subplots(3,1,figsize=(11,13),sharex=True)
    x=list(range(-PRE,POST+1))
    for ax,(name,b) in zip(axs,archetypes.items()):
        a=b["prototype"]
        for m in b["matches"]:
            q=m["event"]
            y=q["pre_raw"]+q["post_raw"][1:]
            ax.plot(x,y,lw=1,alpha=.45,label=f"match {q['day']} t25={outcome_value(q,'exh_t25_s'):.0f}s corr={m['shape_corr']:.2f}")
        y=a["pre_raw"]+a["post_raw"][1:]
        ax.plot(x,y,lw=2.5,label=f"prototype {a['day']} t25={outcome_value(a,'exh_t25_s'):.0f}s")
        ax.axvline(0,ls='--',lw=1)
        ax.axhline(0,lw=.7)
        ax.set_ylabel("dipole mean flow")
        ax.set_title(f"NG-native {name.replace('_',' ')} exhaustion family | roll={roll}s")
        ax.legend(fontsize=7,ncol=2)
        ax.grid(alpha=.25)
    axs[-1].set_xlabel("seconds relative to dipole flip/spike (t=0)")
    plt.tight_layout(); plt.savefig(path,dpi=130); plt.close()


def analyze_roll(days, roll):
    rows=[]
    by_day={}
    for d in days:
        rs=event_rows(d,roll); rows.extend(rs); by_day[d.day]=len(rs)
    if len(rows)<20:
        return {"roll_s":roll,"n":len(rows),"by_day":by_day,"error":"too few dipole-first events"}
    pair=pairwise_similarity_summary(rows)
    knn=cross_day_knn(rows)
    arch=choose_exhaustion_archetypes(rows)
    png=f"ng_native_shape_families_roll{roll}.png"
    render(roll,arch,png)
    return {
        "roll_s":roll,"n":len(rows),"by_day":by_day,
        "exhaustion_t25_quantiles_s":{str(q):quantile([outcome_value(r,'exh_t25_s') for r in rows],q) for q in (.1,.25,.5,.75,.9)},
        "pairwise":pair,"cross_day_5nn":knn,
        "archetypes":{name:{"prototype":compact_event(b["prototype"]),
                            "matches":[{"shape_corr":m["shape_corr"],"amp_similarity":m["amp_similarity"],"event":compact_event(m["event"])} for m in b["matches"]]}
                      for name,b in arch.items()},
        "render":png,
    }


def main(paths):
    days=[load_day(p) for p in paths]
    out={
        "analysis":"NG-native dipole-first shape families; pre-flip similarity -> post-flip exhaustion similarity",
        "construction":{
            "t0":"dipole-only local |flow| spike; price not used for event detection",
            "orientation":"mirror by dipole polarity at t0 only",
            "window":"fixed -60s..0..+60s real seconds",
            "candidate_threshold":"85th percentile day-native |dipole|; local max +/-5s; 45s refractory; ranked by pre-only prominence",
            "roll_windows_s":ROLLS,
            "primary_validation":"cross-day pre-flip curve similarity vs post-flip exhaustion similarity",
            "price_role":"external structural label attached only after dipole event is frozen; direction unused",
        },
        "rolls":{}
    }
    for roll in ROLLS:
        print(f"=== ROLL {roll}s ===",flush=True)
        r=analyze_roll(days,roll); out["rolls"][str(roll)]=r
        print(json.dumps({"roll":roll,"n":r.get("n"),"by_day":r.get("by_day"),
                          "knn":r.get("cross_day_5nn"),
                          "strict":r.get("pairwise",{}).get("strict_same_family_shape_ge_0_90_amp_ge_0_67")},sort_keys=True),flush=True)
    p=Path("ng_dipole_native_shape_audit_results.json")
    p.write_text(json.dumps(out,indent=2,sort_keys=True,allow_nan=True)+"\n")
    print("RESULT_FILE="+str(p),flush=True)

if __name__=="__main__":
    main(sys.argv[1:])
