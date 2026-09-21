#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsRegressor

HORIZONS=("5","10","20","30","60","120","300")
DEPTHS=tuple(range(0,7))
RIDGE_GRID=(0.1,1.0,10.0,100.0,1000.0)
KNN_GRID=(10,20,40,80,160)
TREE_LEAF_GRID=(10,20,40,80)
RANDOM_SEED=20260817


def finite(x):
    try: return math.isfinite(float(x))
    except Exception: return False


def load_rows(path):
    byweek=defaultdict(list)
    with gzip.open(path,"rt") as f:
        for line in f:
            r=json.loads(line)
            # PHASE-1 ACCESS WALL: identity/split + behavioral outcomes only.
            q={
                "event_id":r["event_id"],
                "week_sunday":r["week_sunday"],
                "sequence_index":int(r["sequence_index"]),
                "next_same":r["link"].get("next_same_polarity"),
                "post":r["outcome"].get("post_endpoint_price"),
            }
            byweek[q["week_sunday"]].append(q)
    for w in byweek:
        byweek[w].sort(key=lambda x:x["sequence_index"])
    return dict(byweek)


def behavior_vector(r,view):
    ns=r["next_same"]
    out=[float("nan") if ns is None else (1.0 if int(ns)==1 else -1.0)]
    post=r["post"]
    metrics=("signed_displacement_ticks",) if view=="sparse" else ("signed_displacement_ticks","mfe_ticks","mae_ticks")
    for metric in metrics:
        for h in HORIZONS:
            v=float("nan")
            if post is not None:
                hh=post.get("horizons",{}).get(h,{})
                if not hh.get("censored",False) and finite(hh.get(metric)):
                    v=float(hh[metric])
            out.append(v)
    return out


def make_view(byweek,view):
    arrays={}; valid={}
    for w,rows in byweek.items():
        a=np.asarray([behavior_vector(r,view) for r in rows],float)
        ok=np.all(np.isfinite(a),axis=1)
        b=a.copy()
        b[:,1:]=np.arcsinh(b[:,1:])
        arrays[w]=b; valid[w]=ok
    return arrays,valid


def lag_xy(arr,ok,depth):
    X=[];Y=[];idx=[]
    for t in range(depth,len(arr)):
        if not ok[t]: continue
        if depth and not ok[t-depth:t].all(): continue
        X.append(arr[t-depth:t].reshape(-1) if depth else np.empty(0,float))
        Y.append(arr[t]); idx.append(t)
    return np.asarray(X,float),np.asarray(Y,float),np.asarray(idx,int)


def prep(train_weeks,test_week,depth,arrays,valid):
    tr=[lag_xy(arrays[w],valid[w],depth) for w in train_weeks]
    Xtr=np.vstack([x for x,_,_ in tr]); Ytr=np.vstack([y for _,y,_ in tr])
    Xte,Yte,idx=lag_xy(arrays[test_week],valid[test_week],depth)
    mu=Ytr.mean(axis=0); sd=Ytr.std(axis=0); sd[sd<1e-12]=1.0
    Ytrz=(Ytr-mu)/sd; Ytez=(Yte-mu)/sd
    if depth:
        xm=np.tile(mu,depth); xs=np.tile(sd,depth)
        Xtrz=(Xtr-xm)/xs; Xtez=(Xte-xm)/xs
    else:
        Xtrz=Xtr; Xtez=Xte
    return Xtrz,Ytrz,Xtez,Ytez,idx


def fit_predict(model_name,param,train_weeks,test_week,depth,arrays,valid,inner=False):
    Xtr,Ytr,Xte,Yte,idx=prep(train_weeks,test_week,depth,arrays,valid)
    if depth==0:
        pred=np.zeros_like(Yte)
    elif model_name=="ridge":
        m=Ridge(alpha=float(param),fit_intercept=True)
        m.fit(Xtr,Ytr); pred=m.predict(Xte)
    elif model_name=="knn":
        k=min(int(param),len(Xtr))
        m=KNeighborsRegressor(n_neighbors=k,weights="distance",p=2,n_jobs=-1)
        m.fit(Xtr,Ytr); pred=m.predict(Xte)
    elif model_name=="extra_trees":
        trees=60 if inner else 180
        m=ExtraTreesRegressor(
            n_estimators=trees,min_samples_leaf=int(param),max_features=1.0,
            random_state=RANDOM_SEED,n_jobs=-1,
        )
        m.fit(Xtr,Ytr); pred=m.predict(Xte)
    else:
        raise ValueError(model_name)
    loss=np.mean((Yte-pred)**2,axis=1)
    return {"idx":idx,"loss":loss,"mse":float(loss.mean()),"n":int(len(loss))}


def grid_for(model):
    return RIDGE_GRID if model=="ridge" else (KNN_GRID if model=="knn" else TREE_LEAF_GRID)


def choose_param(model,outer_train,depth,arrays,valid):
    scored=[]
    for p in grid_for(model):
        ms=[]
        for valw in outer_train:
            tr=[w for w in outer_train if w!=valw]
            z=fit_predict(model,p,tr,valw,depth,arrays,valid,inner=True)
            ms.append(z["mse"])
        scored.append((float(np.mean(ms)),p,ms))
    scored.sort(key=lambda x:(x[0],float(x[1])))
    return scored[0],scored


def align_gain(prev,cur,nrows):
    a=np.full(nrows,np.nan); b=np.full(nrows,np.nan)
    a[prev["idx"]]=prev["loss"]; b[cur["idx"]]=cur["loss"]
    return a-b


def fisher_origin_link(g1,d1,g2,d2,n):
    # gD is indexed by TARGET position; align both to the same ORIGIN i.
    aa=[]; bb=[]
    for i in range(n-max(d1,d2)):
        x=g1[i+d1]; y=g2[i+d2]
        if finite(x) and finite(y):
            aa.append(float(x)>0); bb.append(float(y)>0)
    aa=np.asarray(aa,bool); bb=np.asarray(bb,bool)
    tab=np.asarray([
        [np.sum(~aa & ~bb),np.sum(~aa & bb)],
        [np.sum(aa & ~bb),np.sum(aa & bb)],
    ],int)
    odds,p=fisher_exact(tab)
    return {
        "n":int(len(aa)),"table":tab.tolist(),"odds_ratio":float(odds),"p_two_sided":float(p),
        "joint_positive_rate":float(np.mean(aa & bb)),
        "independence_product_rate":float(np.mean(aa)*np.mean(bb)),
        "first_positive_rate":float(np.mean(aa)),"second_positive_rate":float(np.mean(bb)),
    }


def analyze_view(byweek,view):
    arrays,valid=make_view(byweek,view)
    weeks=sorted(byweek)
    models=("ridge","knn","extra_trees")
    final={m:{} for m in models}
    summary={m:{} for m in models}

    for testw in weeks:
        train=[w for w in weeks if w!=testw]
        for m in models:
            summary[m][testw]={}
            final[m][testw]={}
            # D0 is unconditional mean in training-standardized units.
            z0=fit_predict(m,0,train,testw,0,arrays,valid)
            final[m][testw][0]=z0
            summary[m][testw]["0"]={"mse":z0["mse"],"n":z0["n"],"param":None}
            for d in DEPTHS[1:]:
                best,_=choose_param(m,train,d,arrays,valid)
                z=fit_predict(m,best[1],train,testw,d,arrays,valid)
                final[m][testw][d]=z
                summary[m][testw][str(d)]={
                    "mse":z["mse"],"n":z["n"],"param":best[1],
                    "inner_validation_mse":best[0],"inner_week_mse":best[2],
                }

    aggregate={}
    gains={m:{} for m in models}
    for m in models:
        for w in weeks:
            gains[m][w]={}
            n=len(byweek[w])
            for d in DEPTHS[1:]:
                g=align_gain(final[m][w][d-1],final[m][w][d],n)
                gains[m][w][d]=g
                gv=g[np.isfinite(g)]
                summary[m][w][str(d)]["paired_incremental_gain_mean"] = float(gv.mean())
                summary[m][w][str(d)]["paired_incremental_gain_median"] = float(np.median(gv))
                summary[m][w][str(d)]["paired_incremental_gain_positive_rate"] = float(np.mean(gv>0))

    for d in DEPTHS[1:]:
        model_allweek={}
        for m in models:
            vals=[summary[m][w][str(d)]["paired_incremental_gain_mean"] for w in weeks]
            model_allweek[m]={"week_gains":dict(zip(weeks,vals)),"all_weeks_positive":all(x>0 for x in vals)}
        n_models=sum(v["all_weeks_positive"] for v in model_allweek.values())
        aggregate[str(d)]={
            "models":model_allweek,
            "models_positive_all_weeks":n_models,
            "confirmed_all_three_models":bool(n_models==3),
            "candidate_two_of_three_models":bool(n_models>=2),
        }

    lineage={m:{} for m in models}
    for m in models:
        for w in weeks:
            n=len(byweek[w])
            lineage[m][w]={
                "D1_to_D2":fisher_origin_link(gains[m][w][1],1,gains[m][w][2],2,n),
                "D2_to_D3":fisher_origin_link(gains[m][w][2],2,gains[m][w][3],3,n),
            }

    consensus={}
    for w in weeks:
        n=len(byweek[w]); cg={}
        for d in (1,2,3):
            arr=np.full(n,np.nan)
            for t in range(n):
                vals=[gains[m][w][d][t] for m in models]
                if all(finite(x) for x in vals): arr[t]=1.0 if all(float(x)>0 for x in vals) else 0.0
            cg[d]=arr
        consensus[w]={
            "D1_to_D2":fisher_origin_link(cg[1],1,cg[2],2,n),
            "D2_to_D3":fisher_origin_link(cg[2],2,cg[3],3,n),
        }

    return {
        "dimension":int(next(iter(arrays.values())).shape[1]),
        "valid_events_by_week":{w:int(valid[w].sum()) for w in weeks},
        "outer_results":summary,
        "aggregate_depth":aggregate,
        "lineage_association":lineage,
        "all_model_consensus_lineage_association":consensus,
    }, gains


def write_lineage_table(path,byweek,primary_gains):
    models=("ridge","knn","extra_trees")
    with gzip.open(path,"wt") as f:
        for w in sorted(byweek):
            n=len(byweek[w])
            for i,r in enumerate(byweek[w]):
                rec={"origin_event_id":r["event_id"],"week_sunday":w,"sequence_index":i,"incremental_gain":{},"all_models_positive":{}}
                for m in models:
                    rec["incremental_gain"][m]={}
                    for d in (1,2,3):
                        t=i+d
                        g=None if t>=n else primary_gains[m][w][d][t]
                        rec["incremental_gain"][m][str(d)]=None if g is None or not finite(g) else float(g)
                for d in (1,2,3):
                    vals=[rec["incremental_gain"][m][str(d)] for m in models]
                    rec["all_models_positive"][str(d)]=None if any(x is None for x in vals) else bool(all(x>0 for x in vals))
                depth=0
                for d in (1,2,3):
                    if rec["all_models_positive"][str(d)] is True: depth=d
                    else: break
                rec["consecutive_all_models_positive_depth_candidate"]=depth
                f.write(json.dumps(rec,separators=(",",":"),sort_keys=True)+"\n")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("event_table")
    ap.add_argument("--out-prefix",default="NG_EXHAUSTION_CHAIN_PHASE1_DISCOVERY_20260817")
    a=ap.parse_args()
    byweek=load_rows(a.event_table)
    if sorted(byweek)!=["20250713","20250921","20250928"]: raise SystemExit(f"week drift {sorted(byweek)}")
    if sum(len(x) for x in byweek.values())!=12991: raise SystemExit("event-count drift")

    primary,primary_gains=analyze_view(byweek,"full")
    sparse,_=analyze_view(byweek,"sparse")

    result={
        "status":"PHASE1_BEHAVIOR_ONLY_DISCOVERY_COMPLETE",
        "protocol":"research/NG_EXHAUSTION_CHAIN_PHASE1_DISCOVERY_PROTOCOL_20260817.json",
        "event_count":12991,"weeks":sorted(byweek),
        "characteristics_accessed":False,
        "forbidden_characteristics_accessed":[],
        "primary_full_path":primary,
        "sparse_sensitivity":sparse,
        "interpretation_guard":"Phase 1 may freeze chain depth/boundaries only. Family/flow/book/time/session and other characteristics remain sealed until Phase 2.",
        "runway_clock_mutated":False,"permanent_frankie_mutated":False,
    }
    Path(a.out_prefix+"_SUMMARY.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    write_lineage_table(a.out_prefix+"_LINEAGE.jsonl.gz",byweek,primary_gains)
    print(json.dumps({
        "status":result["status"],
        "primary_aggregate":primary["aggregate_depth"],
        "primary_consensus_lineage":primary["all_model_consensus_lineage_association"],
        "sparse_aggregate":sparse["aggregate_depth"],
    },indent=2,sort_keys=True))

if __name__=="__main__": main()
