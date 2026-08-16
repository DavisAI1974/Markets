"""Quantify Greg's pre-flip hockey-stick hypothesis on NG.

Locked before outcomes are read:
  1) HEIGHT: low early dipole -> high t=0 spike.
  2) LENGTH: how early the rise begins before t=0.
  3) BEND: final-10s steepening versus the prior 20s.
  4) RAMPINESS: straight-line fit across the left window.

Hypothesis: larger height + longer build + stronger late bend => longer post-flip
exhaustion; a more linear ramp => shorter exhaustion.

Dipole is oriented only by its own t=0 polarity. Price direction never enters the
curve. Price is used only for retrospective leg-duration labels.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from statistics import median

from ng_dipole_runway_audit import load_day, mean, corr, rankdata
from ng_preflip_exhaustion_archetypes import event_rows

PERSIST=3


def spearman(x,y):
    p=[(float(a),float(b)) for a,b in zip(x,y) if math.isfinite(float(a)) and math.isfinite(float(b))]
    if len(p)<3:return float('nan')
    rx=rankdata([a for a,_ in p]); ry=rankdata([b for _,b in p])
    return corr(rx,ry)


def linfit_r2(y):
    pts=[(i,float(v)) for i,v in enumerate(y) if math.isfinite(float(v))]
    if len(pts)<5:return float('nan')
    xs=[a for a,_ in pts]; ys=[b for _,b in pts]
    mx,my=mean(xs),mean(ys); den=sum((x-mx)**2 for x in xs)
    if den<=0:return float('nan')
    b=sum((x-mx)*(v-my) for x,v in zip(xs,ys))/den; a=my-b*mx
    ss=sum((v-my)**2 for v in ys)
    if ss<=0:return 1.0
    er=sum((v-(a+b*x))**2 for x,v in zip(xs,ys))
    return 1-er/ss


def seg_slope(y,i0,i1):
    pts=[(i,float(y[i])) for i in range(i0,i1+1) if math.isfinite(float(y[i]))]
    if len(pts)<3:return float('nan')
    xs=[a for a,_ in pts]; ys=[b for _,b in pts]
    mx,my=mean(xs),mean(ys); den=sum((x-mx)**2 for x in xs)
    return sum((x-mx)*(v-my) for x,v in zip(xs,ys))/den if den else 0.0


def first_persist_cross(y, level):
    for i in range(0,len(y)-PERSIST+1):
        w=y[i:i+PERSIST]
        if all(math.isfinite(float(v)) and float(v)>=level for v in w): return i
    return None


def metrics(r):
    pre=[float(v) for v in r['pre']]
    peak=float(r['peak'])
    early=[v for v in pre[:16] if math.isfinite(v)]   # -60..-45s
    base=mean(early) if early else float('nan')
    low=min(v for v in pre if math.isfinite(v))
    height_abs=peak-base
    height_from_low_abs=peak-low
    height_norm=height_abs/peak if peak else float('nan')
    height_from_low_norm=height_from_low_abs/peak if peak else float('nan')

    # Rise clock is defined relative to the early baseline and t=0 spike, not outcome.
    c10=first_persist_cross(pre, base+0.10*height_abs) if height_abs>0 else None
    c25=first_persist_cross(pre, base+0.25*height_abs) if height_abs>0 else None
    c50=first_persist_cross(pre, base+0.50*height_abs) if height_abs>0 else None
    c90=first_persist_cross(pre, base+0.90*height_abs) if height_abs>0 else None
    build10_s=(60-c10) if c10 is not None else 0
    build25_s=(60-c25) if c25 is not None else 0
    climb10_90_s=(c90-c10) if c10 is not None and c90 is not None else None

    norm=[v/peak if math.isfinite(v) and peak else float('nan') for v in pre]
    s_prev=seg_slope(norm,30,50)   # -30..-10
    s_last=seg_slope(norm,50,60)   # -10..0
    bend=s_last-s_prev if math.isfinite(s_last) and math.isfinite(s_prev) else float('nan')
    slope_ratio=(s_last/(abs(s_prev)+1e-9)) if math.isfinite(s_last) and math.isfinite(s_prev) else float('nan')
    path=sum(abs(norm[i]-norm[i-1]) for i in range(1,len(norm)) if math.isfinite(norm[i]) and math.isfinite(norm[i-1]))

    return {
      'early_baseline_raw':base,
      'pre_min_raw':low,
      't0_peak_raw':peak,
      'low_to_high_height_abs':height_abs,
      'min_to_peak_height_abs':height_from_low_abs,
      'low_to_high_height_norm':height_norm,
      'min_to_peak_height_norm':height_from_low_norm,
      'build_from_10pct_s':build10_s,
      'build_from_25pct_s':build25_s,
      'climb_10_to_90_s':climb10_90_s,
      'slope_m30_m10_norm':s_prev,
      'slope_m10_0_norm':s_last,
      'late_bend_score':bend,
      'late_slope_ratio':slope_ratio,
      'left_linearity_r2':linfit_r2(norm),
      'left_path_length_norm':path,
    }


def rankavg(rows, names):
    cols={n:[r['hockey'][n] for r in rows] for n in names}
    ranks={n:rankdata(v) for n,v in cols.items()}
    return [mean([ranks[n][i] for n in names]) for i in range(len(rows))]


def summarize(rows):
    for r in rows:r['hockey']=metrics(r)
    dur=[r['leg_duration_s'] for r in rows]
    exh25=[r['exh_t25_s'] if r['exh_t25_s'] is not None else 61 for r in rows]
    exhzero=[r['exh_zero_s'] if r['exh_zero_s'] is not None else 61 for r in rows]
    names=list(rows[0]['hockey'])
    assoc={}
    for n in names:
        x=[r['hockey'][n] for r in rows]
        assoc[n]={
          'spearman_leg_duration':spearman(x,dur),
          'spearman_exh_t25_censored61':spearman(x,exh25),
          'spearman_exh_zero_censored61':spearman(x,exhzero),
        }

    # Equal-rank composite, locked: height + build length + late bend. No learned weights.
    comp=rankavg(rows,['low_to_high_height_norm','build_from_10pct_s','late_bend_score'])
    ramp=[r['hockey']['left_linearity_r2'] for r in rows]

    # Cross-day 5NN using ONLY the four visual left-side hockey descriptors.
    fns=['low_to_high_height_norm','build_from_10pct_s','late_bend_score','left_linearity_r2']
    pred_ex=[]; true_ex=[]; pred_d=[]; true_d=[]
    for r in rows:
        pool=[q for q in rows if q['day']!=r['day']]
        if len(pool)<5:continue
        # rank-standardize by full scratch sample for distance only; no outcomes involved
        vals={n:[q['hockey'][n] for q in rows] for n in fns}
        mu={n:mean([v for v in vals[n] if math.isfinite(v)]) for n in fns}
        sd={}
        for n in fns:
            vv=[v for v in vals[n] if math.isfinite(v)]; m=mu[n]
            sd[n]=(sum((v-m)**2 for v in vv)/len(vv))**0.5 if vv else 1.0
            if sd[n]<1e-9:sd[n]=1.0
        def dist(q):
            s=0; k=0
            for n in fns:
                a=r['hockey'][n]; b=q['hockey'][n]
                if math.isfinite(a) and math.isfinite(b):
                    s+=((a-b)/sd[n])**2;k+=1
            return (s/k)**0.5 if k else 1e9
        nn=sorted(pool,key=dist)[:5]
        pred_ex.append(median([(q['exh_t25_s'] if q['exh_t25_s'] is not None else 61) for q in nn]))
        true_ex.append(r['exh_t25_s'] if r['exh_t25_s'] is not None else 61)
        pred_d.append(median([q['leg_duration_s'] for q in nn])); true_d.append(r['leg_duration_s'])

    return {
      'n':len(rows),
      'locked_hypothesis':'greater low-to-high height + earlier/longer build + stronger late bend => longer exhaustion; higher straight-line ramp R2 => shorter exhaustion',
      'metric_associations':assoc,
      'hockey_equal_rank_composite':{
        'spearman_leg_duration':spearman(comp,dur),
        'spearman_exh_t25_censored61':spearman(comp,exh25),
        'spearman_exh_zero_censored61':spearman(comp,exhzero),
      },
      'ramp_linearity':{
        'spearman_leg_duration':spearman(ramp,dur),
        'spearman_exh_t25_censored61':spearman(ramp,exh25),
        'spearman_exh_zero_censored61':spearman(ramp,exhzero),
      },
      'cross_day_hockey_5nn':{
        'n':len(pred_ex),
        'spearman_predicted_vs_actual_exh_t25':spearman(pred_ex,true_ex),
        'spearman_predicted_vs_actual_leg_duration':spearman(pred_d,true_d),
        'mae_exh_t25_s':mean([abs(a-b) for a,b in zip(pred_ex,true_ex)]),
        'mae_leg_duration_s':mean([abs(a-b) for a,b in zip(pred_d,true_d)]),
      },
    }


def main(paths):
    rows=[]
    for p in paths:rows.extend(event_rows(load_day(p)))
    out={'definition':{
      'window':'-60s..0..+60s, t=0 dipole flip/spike',
      'price_direction_in_curve':False,
      'hockey_height':'t0 spike minus mean dipole over -60..-45s',
      'hockey_length':'seconds from first persistent 10%/25% rise above early baseline to t=0',
      'hockey_bend':'normalized slope(-10..0) minus slope(-30..-10)',
      'rampiness':'R2 of straight line fit across normalized -60..0 curve',
      'post_target':'dipole exhaustion only; t25/zero censored at >60s as 61 for rank tests',
    },'summary':summarize(rows)}
    p=Path('ng_hockeystick_exhaustion_results.json');p.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(out,indent=2,sort_keys=True));print('RESULT_FILE='+str(p))

if __name__=='__main__':
    if len(sys.argv)<2:raise SystemExit('pass NG raw day files')
    main(sys.argv[1:])
