#!/usr/bin/env python3
from __future__ import annotations

import gzip, hashlib, json, math, sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.preprocessing import RobustScaler

import ng_exhaustion_family_quantify_v2_20260816 as fam
import ng_exhaustion_frankie_blind_input_20260816 as blind
from ng_dipole_native_shape_audit import event_rows
from ng_dipole_runway_audit import TICK, load_day, zigzag_legs

FREEZE_DIR = Path("research/blind_freeze/ng_exhaustion_20260816")
FREEZE_MANIFEST = FREEZE_DIR / "FRANKIE_NG_EXHAUSTION_BLIND_PREDICTION_FREEZE_MANIFEST_20260816.json"
FREEZE_COMMIT = "0f26c125548c801037bb3084d23b1b5d974ae0eb"
THRESHOLDS = (3, 5, 8, 13)

def finite(x):
    try: return math.isfinite(float(x))
    except Exception: return False

def sign(x, eps=1e-12):
    x=float(x); return 1 if x>eps else (-1 if x<-eps else 0)

def median(xs):
    a=[float(x) for x in xs if finite(x)]
    return float(np.median(a)) if a else None

def mean(xs):
    a=[float(x) for x in xs if finite(x)]
    return float(np.mean(a)) if a else None

def containing_leg(legs, t):
    for leg in legs:
        if int(leg["start"]) <= t <= int(leg["end"]): return leg
    return None

def load_predictions():
    m=json.loads(FREEZE_MANIFEST.read_text())
    if m.get("status") != "FROZEN_BLIND_PREDICTIONS_PENDING_REVEAL": raise SystemExit("prediction freeze manifest status invalid")
    if int(m.get("prediction_n",-1)) != 1711: raise SystemExit("prediction freeze count invalid")
    if m.get("outcome_accessed_before_freeze") is not False or m.get("future_price_served_to_model") is not False: raise SystemExit("prediction freeze outcome wall invalid")
    if m.get("single_best_curve_only") is not True or m.get("uncertainty_bands") is not False: raise SystemExit("prediction curve contract invalid")
    out={}
    for name, meta in m["shards"].items():
        p=FREEZE_DIR/name; b=p.read_bytes(); got=hashlib.sha256(b).hexdigest()
        if got != meta["sha256"]: raise SystemExit(f"prediction shard digest drift {name}: {got}")
        with gzip.open(p,"rt") as f: raw=f.read()
        if hashlib.sha256(raw.encode()).hexdigest() != meta["uncompressed_sha256"]: raise SystemExit(f"prediction shard uncompressed digest drift {name}")
        rows=[json.loads(line) for line in raw.splitlines() if line.strip()]
        if len(rows) != int(meta["records"]): raise SystemExit(f"prediction shard record drift {name}")
        for r in rows:
            bid=r["blind_id"]
            if bid in out: raise SystemExit(f"duplicate prediction id {bid}")
            if r.get("outcome_accessed") is not False: raise SystemExit(f"outcome flag violation {bid}")
            curve=r.get("path_price_curve")
            if not isinstance(curve,list) or len(curve)<2 or float(curve[0][0]) != 0: raise SystemExit(f"curve contract violation {bid}")
            if abs(float(curve[0][1])-float(r["price_anchor"])) > 1e-12: raise SystemExit(f"anchor mismatch {bid}")
            out[bid]=r
    if len(out)!=1711: raise SystemExit(f"prediction population drift {len(out)}")
    return m,out

def rebuild_holdout(paths):
    days={}; rows=[]
    for p in paths:
        d=load_day(p); days[d.day]=d; rows.extend(event_rows(d, blind.ROLL))
    if tuple(sorted(days)) != blind.TARGET_DAYS: raise SystemExit(f"target-day drift {tuple(sorted(days))}")
    X0=np.vstack([fam.feature(r) for r in rows]); X=RobustScaler(quantile_range=(20,80)).fit_transform(X0)
    _,l4,_,_=fam.fit_balanced(X,4); cnt=Counter(map(int,l4)); one=[c for c,n in cnt.items() if n==1]
    if len(one)!=1: raise SystemExit(f"singleton invariant {cnt}")
    rows=[r for r,z in zip(rows,l4) if int(z)!=one[0]]
    X0=np.vstack([fam.feature(r) for r in rows]); X=RobustScaler(quantile_range=(20,80)).fit_transform(X0)
    centers,l3,_,_=fam.fit_balanced(X,3); l3,centers,_=fam.deterministic_order(rows,l3,centers)
    names={0:"A",1:"B",2:"C"}; strata=defaultdict(list)
    for i,(r,z) in enumerate(zip(rows,l3)): strata[(int(z),r["day"])].append((blind.split_key(r,int(z)),i))
    hold=set()
    for items in strata.values():
        items.sort(); nrev=(len(items)+1)//2; hold.update(i for _,i in items[nrev:])
    if len(hold)!=1711: raise SystemExit(f"holdout split drift {len(hold)}")
    return days,[(r,names[int(z)]) for i,(r,z) in enumerate(zip(rows,l3)) if i in hold]

def interp_forecast(curve, seconds):
    xs=np.asarray([float(p[0]) for p in curve],float); ys=np.asarray([float(p[1]) for p in curve],float)
    return float(np.interp(float(seconds),xs,ys))

def actual_at(day, t0, dt):
    i=t0+int(round(dt))
    if i<0 or i>=len(day.price): return None
    v=day.price[i]; return float(v) if finite(v) else None

def curve_metrics(pred, day, t0):
    curve=pred["path_price_curve"]; anchor=float(pred["price_anchor"]); node_err=[]
    for dt,fp in curve:
        ap=actual_at(day,t0,float(dt))
        if ap is not None: node_err.append((float(fp)-ap)/TICK)
    end=int(round(float(curve[-1][0]))); max_end=min(end, len(day.price)-1-t0)
    grid=list(range(0,max_end+1,30))
    if not grid or grid[-1] != max_end: grid.append(max_end)
    fgrid=[]; agrid=[]
    for dt in grid:
        ap=actual_at(day,t0,dt)
        if ap is None: continue
        fgrid.append(interp_forecast(curve,dt)); agrid.append(ap)
    corr=None
    if len(fgrid)>=3 and np.std(fgrid)>1e-12 and np.std(agrid)>1e-12: corr=float(np.corrcoef(fgrid,agrid)[0,1])
    pred_mag=max(abs(float(p[1])-anchor) for p in curve)/TICK
    actual_vals=[day.price[t0+i] for i in range(max_end+1) if finite(day.price[t0+i])]
    actual_mag=max((abs(float(x)-anchor) for x in actual_vals),default=float("nan"))/TICK
    f60=interp_forecast(curve,min(60,end)); a60=actual_at(day,t0,min(60,end)); fend=float(curve[-1][1]); aend=actual_at(day,t0,max_end)
    return {"node_mae_ticks":mean([abs(x) for x in node_err]),"node_rmse_ticks":float(math.sqrt(np.mean(np.square(node_err)))) if node_err else None,"curve_corr_30s":corr,"pred_max_abs_ticks":float(pred_mag),"actual_max_abs_ticks":float(actual_mag) if finite(actual_mag) else None,"magnitude_abs_error_ticks":abs(float(pred_mag)-float(actual_mag)) if finite(actual_mag) else None,"direction_60_correct":None if a60 is None else int(sign(f60-anchor)==sign(a60-anchor)),"terminal_direction_correct":None if aend is None else int(sign(fend-anchor)==sign(aend-anchor)),"forecast_horizon_s":end,"actual_terminal_price":aend,"forecast_terminal_price":fend}

def summarize(rows, keyfunc):
    groups=defaultdict(list)
    for r in rows: groups[keyfunc(r)].append(r)
    out={}
    for k,rr in sorted(groups.items()):
        g={"n":len(rr)}
        for fld in ("node_mae_ticks","node_rmse_ticks","curve_corr_30s","magnitude_abs_error_ticks"):
            vals=[x["curve_metrics"].get(fld) for x in rr]; g[f"{fld}_median"]=median(vals); g[f"{fld}_mean"]=mean(vals)
        for fld in ("direction_60_correct","terminal_direction_correct"):
            vals=[x["curve_metrics"].get(fld) for x in rr if x["curve_metrics"].get(fld) is not None]; g[f"{fld}_rate"]=mean(vals); g[f"{fld}_n"]=len(vals)
        g["duration"]={}
        for th in THRESHOLDS:
            kk=f"{th}t"; paired=[x for x in rr if x["actual_legs"].get(kk) is not None]
            predv=[x["predicted_duration_s"].get(kk) for x in paired]; actv=[x["actual_legs"][kk]["duration_s"] for x in paired]
            abs_err=[abs(float(a)-float(p)) for a,p in zip(actv,predv) if finite(a) and finite(p)]; rho=None
            valid=[(float(a),float(p)) for a,p in zip(actv,predv) if finite(a) and finite(p)]
            if len(valid)>=3 and len(set(p for _,p in valid))>1 and len(set(a for a,_ in valid))>1: rho=float(spearmanr([p for a,p in valid],[a for a,p in valid]).statistic)
            g["duration"][kk]={"n":len(paired),"pred_median_s":median(predv),"actual_median_s":median(actv),"mae_s":mean(abs_err),"median_abs_error_s":median(abs_err),"spearman":rho}
        out[k]=g
    return out

def actual_alignment(rows, family, th):
    rr=[r for r in rows if r["family"]==family and r["actual_legs"].get(f"{th}t") is not None]
    vals=[int(int(r["actual_legs"][f"{th}t"]["direction"])==int(r["dipole_polarity"])) for r in rr]
    return {"n":len(vals),"rate":mean(vals)}

def a_state_order(rows):
    out={"pooled":{},"daily":{}}
    for th in THRESHOLDS:
        kk=f"{th}t"; st={}
        for state in ("A-fast-collapse","A-persistent"):
            vals=[r["actual_legs"][kk]["duration_s"] for r in rows if r["post_state"]==state and r["actual_legs"].get(kk)]
            st[state]={"n":len(vals),"median_s":median(vals)}
        st["persistent_gt_collapse"]=(st["A-persistent"]["median_s"] is not None and st["A-fast-collapse"]["median_s"] is not None and st["A-persistent"]["median_s"]>st["A-fast-collapse"]["median_s"]); out["pooled"][kk]=st
    for day in sorted(set(r["day"] for r in rows)):
        out["daily"][day]={}
        for th in THRESHOLDS:
            kk=f"{th}t"; st={}
            for state in ("A-fast-collapse","A-persistent"):
                vals=[r["actual_legs"][kk]["duration_s"] for r in rows if r["day"]==day and r["post_state"]==state and r["actual_legs"].get(kk)]; st[state]=median(vals)
            st["persistent_gt_collapse"]=(st["A-persistent"] is not None and st["A-fast-collapse"] is not None and st["A-persistent"]>st["A-fast-collapse"]); out["daily"][day][kk]=st
    return out

def group_name(r): return r["post_state"] if r["family"]=="A" else r["family"]

def render_group(rows, group, outpath):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    rr=[r for r in rows if group_name(r)==group]; horizon=int(median([r["curve_metrics"]["forecast_horizon_s"] for r in rr]) or 0); grid=np.arange(0,horizon+1,30,dtype=int); fmat=[]; amat=[]
    for r in rr:
        curve=r["_pred_curve"]; anchor=float(r["price_anchor"]); day=r["_day"]; t0=int(r["t0_second_utc"]); fv=[]; av=[]
        for dt in grid:
            fv.append((interp_forecast(curve,int(dt))-anchor)/TICK); ap=actual_at(day,t0,int(dt)); av.append(np.nan if ap is None else (ap-anchor)/TICK)
        fmat.append(fv); amat.append(av)
    fmed=np.nanmedian(np.asarray(fmat,float),axis=0); amed=np.nanmedian(np.asarray(amat,float),axis=0); fig=plt.figure(figsize=(10,5.5)); plt.plot(grid,fmed,label="Frankie forecast median"); plt.plot(grid,amed,label="Actual median"); plt.axhline(0,linewidth=.8); plt.xlabel("Seconds from t0"); plt.ylabel("Ticks from t0 anchor"); plt.title(f"Frankie blind vs actual — {group} (n={len(rr)})"); plt.legend(); plt.tight_layout(); fig.savefig(outpath,dpi=170); plt.close(fig)

def render_representative(rows, group, outpath):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    rr=[r for r in rows if group_name(r)==group and finite(r["curve_metrics"]["node_rmse_ticks"])]; rr=sorted(rr,key=lambda r:float(r["curve_metrics"]["node_rmse_ticks"])); r=rr[len(rr)//2]; curve=r["_pred_curve"]; day=r["_day"]; t0=int(r["t0_second_utc"]); horizon=int(curve[-1][0]); max_end=min(horizon,len(day.price)-1-t0); grid=np.arange(0,max_end+1,5,dtype=int); actual=np.asarray([(float(day.price[t0+i]) if finite(day.price[t0+i]) else np.nan) for i in grid]); fx=[float(p[0]) for p in curve]; fy=[float(p[1]) for p in curve]; fig=plt.figure(figsize=(10,5.5)); plt.plot(grid,actual,label="Actual"); plt.plot(fx,fy,marker="o",label="Frankie forecast"); plt.xlabel("Seconds from t0"); plt.ylabel("NG price"); plt.title(f"Representative blind curve — {group} — {r['day']} {r['blind_id']}"); plt.legend(); plt.tight_layout(); fig.savefig(outpath,dpi=170); plt.close(fig); return r["blind_id"]

def main(paths):
    manifest,preds=load_predictions(); days,held=rebuild_holdout(paths)
    if Counter(f for _,f in held) != Counter({"A":1616,"B":35,"C":60}): raise SystemExit("heldout family counts drift")
    pred_ids=set(preds); rebuilt_ids={blind.blind_id(r) for r,_ in held}
    if rebuilt_ids != pred_ids: raise SystemExit(f"heldout id mismatch missing_pred={len(rebuilt_ids-pred_ids)} extra_pred={len(pred_ids-rebuilt_ids)}")
    legs_by_day={day:{th:zigzag_legs(d.price,th) for th in THRESHOLDS} for day,d in days.items()}; results=[]
    for r,family in held:
        bid=blind.blind_id(r); pred=preds[bid]; day=days[r["day"]]; t0=int(r["flip_s"])
        if pred["family"] != family or int(pred["t0_second_utc"]) != t0: raise SystemExit(f"prediction identity drift {bid}")
        anchor=actual_at(day,t0,0)
        if anchor is None or abs(float(pred["price_anchor"])-anchor)>1e-12: raise SystemExit(f"prediction anchor drift {bid}")
        actual_legs={}
        for th in THRESHOLDS:
            leg=containing_leg(legs_by_day[r["day"]][th],t0); actual_legs[f"{th}t"]=None if leg is None else {"start_s":int(leg["start"]),"end_s":int(leg["end"]),"duration_s":int(leg["duration"]),"remaining_from_t0_s":int(max(0,int(leg["end"])-t0)),"direction":int(leg["dir"]),"ticks":float(leg["ticks"]),"aligned_with_dipole":bool(int(leg["dir"])==int(r["dipole_polarity"]))}
        cm=curve_metrics(pred,day,t0); results.append({"blind_id":bid,"family":family,"day":r["day"],"t0_second_utc":t0,"dipole_polarity":int(r["dipole_polarity"]),"price_anchor":anchor,"post_state":pred.get("post_state"),"confidence":pred.get("confidence"),"predicted_duration_s":pred["predicted_duration_s"],"actual_legs":actual_legs,"curve_metrics":cm,"microstructure_read":pred.get("microstructure_read"),"directional_scale_projection":pred.get("directional_scale_projection"),"reasoning":pred.get("reasoning"),"brain_attribution":pred.get("brain_attribution"),"_pred_curve":pred["path_price_curve"],"_day":day})
    summary={"status":"REVEALED_AND_SCORED_AFTER_FROZEN_PREDICTIONS","prediction_freeze_commit":FREEZE_COMMIT,"prediction_n":len(results),"prediction_artifact_input_digest":manifest["input_artifact_digest"],"family_counts":dict(Counter(r["family"] for r in results)),"post_state_counts":dict(Counter(r["post_state"] for r in results if r["post_state"])),"by_group":summarize(results,group_name),"by_family":summarize(results,lambda r:r["family"]),"a_state_realized_ordering":a_state_order(results),"B_alignment":{f"{th}t":actual_alignment(results,"B",th) for th in THRESHOLDS},"C_alignment":{f"{th}t":actual_alignment(results,"C",th) for th in THRESHOLDS},"no_retuning":True}
    clean=[{k:v for k,v in r.items() if not k.startswith("_")} for r in results]
    with gzip.open("frankie_ng_blind_reveal_event_scores.jsonl.gz","wt") as f:
        for r in clean: f.write(json.dumps(r,separators=(",",":"))+"\n")
    render_ids={}
    for group in ("A-persistent","A-fast-collapse","B","C"):
        safe=group.replace("-","_"); render_group(results,group,f"frankie_blind_group_{safe}.png"); render_ids[group]=render_representative(results,group,f"frankie_blind_representative_{safe}.png")
    summary["representative_blind_ids"]=render_ids; Path("FRANKIE_NG_EXHAUSTION_BLIND_REVEAL_SCORECARD_20260816.json").write_text(json.dumps(summary,indent=2)+"\n")
    print(json.dumps({"status":summary["status"],"prediction_n":len(results),"family_counts":summary["family_counts"],"post_state_counts":summary["post_state_counts"],"a_3t":summary["a_state_realized_ordering"]["pooled"]["3t"],"a_5t":summary["a_state_realized_ordering"]["pooled"]["5t"],"a_8t":summary["a_state_realized_ordering"]["pooled"]["8t"]},indent=2))

if __name__=="__main__": main(sys.argv[1:])
