#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from sklearn.ensemble import ExtraTreesRegressor
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsRegressor

HORIZONS=(5,10,20,30,60,120,300)
DEPTHS=(1,2,3,4,5,6)
RIDGE_GRID=(0.1,1.0,10.0,100.0,1000.0)
KNN_GRID=(10,20,40,80,160)
TREE_GRID=(10,20,40,80)
SEED=20260817


def finite(x):
    try: return math.isfinite(float(x))
    except Exception: return False


def load_rows(path):
    byweek=defaultdict(list)
    with gzip.open(path,'rt') as f:
        for line in f:
            r=json.loads(line)
            # Phase-1 causal access wall: timing only for availability, never as a model feature.
            q={
                'event_id':r['event_id'],
                'week_sunday':r['week_sunday'],
                'sequence_index':int(r['sequence_index']),
                't0_idx':int(r['t0_idx']),
                'endpoint_confirm_idx':r['dynamic_endpoint'].get('causal_confirmation_idx'),
                'next_same':r['link'].get('next_same_polarity'),
                'post':r['outcome'].get('post_endpoint_price'),
            }
            byweek[q['week_sunday']].append(q)
    for w in byweek: byweek[w].sort(key=lambda r:r['sequence_index'])
    return dict(byweek)


def full_target(r):
    ns=r['next_same']; out=[float('nan') if ns is None else (1.0 if int(ns)==1 else -1.0)]
    post=r['post']
    for metric in ('signed_displacement_ticks','mfe_ticks','mae_ticks'):
        for h in HORIZONS:
            v=float('nan')
            if post is not None:
                z=post.get('horizons',{}).get(str(h),{})
                if not z.get('censored',False) and finite(z.get(metric)): v=float(z[metric])
            out.append(v)
    a=np.asarray(out,float)
    if np.all(np.isfinite(a)): a[1:]=np.arcsinh(a[1:])
    return a


def causal_input(r,hmax):
    ns=r['next_same']; out=[float('nan') if ns is None else (1.0 if int(ns)==1 else -1.0)]
    post=r['post']
    hs=[h for h in HORIZONS if h<=hmax]
    for metric in ('signed_displacement_ticks','mfe_ticks','mae_ticks'):
        for h in hs:
            v=float('nan')
            if post is not None:
                z=post.get('horizons',{}).get(str(h),{})
                if not z.get('censored',False) and finite(z.get(metric)): v=float(z[metric])
            out.append(v)
    a=np.asarray(out,float)
    if np.all(np.isfinite(a)): a[1:]=np.arcsinh(a[1:])
    return a


def eligible_indices(rows,hmax,max_depth):
    targ=[full_target(r) for r in rows]
    inp=[causal_input(r,hmax) for r in rows]
    idx=[]
    for t in range(max_depth,len(rows)):
        if not np.all(np.isfinite(targ[t])): continue
        ok=True
        for j in range(t-max_depth,t):
            if not np.all(np.isfinite(inp[j])):
                ok=False; break
            c=rows[j]['endpoint_confirm_idx']
            if c is None or int(c)+int(hmax)>int(rows[t]['t0_idx']):
                ok=False; break
        if ok: idx.append(t)
    return np.asarray(idx,int),targ,inp


def matrices(rows,hmax,max_depth,history_len):
    idx,targ,inp=eligible_indices(rows,hmax,max_depth)
    Y=np.vstack([targ[t] for t in idx]) if len(idx) else np.empty((0,22),float)
    if history_len==0:
        X=np.empty((len(idx),0),float)
    else:
        X=np.vstack([np.concatenate(inp[t-history_len:t]) for t in idx]) if len(idx) else np.empty((0,0),float)
    return X,Y,idx


def prepare(train_weeks,test_week,hmax,max_depth,history_len,byweek):
    trs=[matrices(byweek[w],hmax,max_depth,history_len) for w in train_weeks]
    Xtr=np.vstack([z[0] for z in trs]); Ytr=np.vstack([z[1] for z in trs])
    Xte,Yte,idx=matrices(byweek[test_week],hmax,max_depth,history_len)
    if len(Ytr)==0 or len(Yte)==0: return None
    ym=Ytr.mean(axis=0); ys=Ytr.std(axis=0); ys[ys<1e-12]=1.0
    Ytr=(Ytr-ym)/ys; Yte=(Yte-ym)/ys
    if history_len:
        xm=Xtr.mean(axis=0); xs=Xtr.std(axis=0); xs[xs<1e-12]=1.0
        Xtr=(Xtr-xm)/xs; Xte=(Xte-xm)/xs
    return Xtr,Ytr,Xte,Yte,idx


def grid(model):
    return RIDGE_GRID if model=='ridge' else (KNN_GRID if model=='knn' else TREE_GRID)


def score(model,param,train_weeks,test_week,hmax,max_depth,history_len,byweek,inner=False):
    z=prepare(train_weeks,test_week,hmax,max_depth,history_len,byweek)
    if z is None: return None
    Xtr,Ytr,Xte,Yte,idx=z
    if history_len==0:
        pred=np.zeros_like(Yte)
    elif model=='ridge':
        m=Ridge(alpha=float(param)); m.fit(Xtr,Ytr); pred=m.predict(Xte)
    elif model=='knn':
        k=min(int(param),len(Xtr)); m=KNeighborsRegressor(n_neighbors=k,weights='distance',n_jobs=-1); m.fit(Xtr,Ytr); pred=m.predict(Xte)
    elif model=='extra_trees':
        m=ExtraTreesRegressor(n_estimators=50 if inner else 140,min_samples_leaf=int(param),max_features=1.0,random_state=SEED,n_jobs=-1)
        m.fit(Xtr,Ytr); pred=m.predict(Xte)
    else: raise ValueError(model)
    loss=np.mean((Yte-pred)**2,axis=1)
    return {'idx':idx,'loss':loss,'mse':float(loss.mean()),'n':int(len(loss))}


def tune(model,outer_train,hmax,max_depth,history_len,byweek):
    if history_len==0: return None
    candidates=[]
    for p in grid(model):
        vals=[]; valid=True
        for vw in outer_train:
            tr=[w for w in outer_train if w!=vw]
            z=score(model,p,tr,vw,hmax,max_depth,history_len,byweek,inner=True)
            if z is None: valid=False; break
            vals.append(z['mse'])
        if valid: candidates.append((float(np.mean(vals)),p,vals))
    if not candidates: return None
    candidates.sort(key=lambda x:(x[0],float(x[1])))
    return candidates[0]


def analyze(byweek):
    weeks=sorted(byweek); models=('ridge','knn','extra_trees'); out={}
    for h in HORIZONS:
        hz={'depth':{},'eligibility_by_week':{}}
        for d in DEPTHS:
            hz['eligibility_by_week'][str(d)]={w:int(len(eligible_indices(byweek[w],h,d)[0])) for w in weeks}
            md={}
            for model in models:
                wg={}; allpos=True
                for testw in weeks:
                    tr=[w for w in weeks if w!=testw]
                    short=d-1
                    ps=tune(model,tr,h,d,short,byweek) if short>0 else None
                    pl=tune(model,tr,h,d,d,byweek)
                    if pl is None or (short>0 and ps is None):
                        wg[testw]={'n':0,'gain_mean':None}; allpos=False; continue
                    zs=score(model,None if short==0 else ps[1],tr,testw,h,d,short,byweek)
                    zl=score(model,pl[1],tr,testw,h,d,d,byweek)
                    if zs is None or zl is None or not np.array_equal(zs['idx'],zl['idx']):
                        raise SystemExit(f'paired-sample invariant failed h={h} d={d} {model} {testw}')
                    gain=zs['loss']-zl['loss']
                    gm=float(gain.mean()); allpos=allpos and gm>0
                    wg[testw]={
                        'n':int(len(gain)),'short_history':short,'long_history':d,
                        'short_param':None if short==0 else ps[1],'long_param':pl[1],
                        'short_mse':zs['mse'],'long_mse':zl['mse'],
                        'gain_mean':gm,'gain_median':float(np.median(gain)),'gain_positive_rate':float(np.mean(gain>0)),
                    }
                md[model]={'weeks':wg,'all_weeks_positive':bool(allpos)}
            npos=sum(int(md[m]['all_weeks_positive']) for m in models)
            hz['depth'][str(d)]={
                'models':md,'models_positive_all_weeks':npos,
                'confirmed_all_three_models':bool(npos==3),
                'candidate_two_of_three_models':bool(npos>=2),
            }
        out[str(h)]=hz
    return out


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('event_table'); ap.add_argument('--out',default='NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_20260817.json'); a=ap.parse_args()
    byweek=load_rows(a.event_table)
    if sorted(byweek)!=['20250713','20250921','20250928']: raise SystemExit('week drift')
    if sum(map(len,byweek.values()))!=12991: raise SystemExit('event-count drift')
    result={
        'status':'PHASE1_CAUSAL_EXECUTABLE_HIGHER_ORDER_COMPLETE',
        'protocol':'research/NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_PROTOCOL_20260817.json',
        'event_count':12991,'weeks':sorted(byweek),
        'characteristics_accessed':False,
        'timing_accessed_only_for_causal_availability':True,
        'by_information_horizon_seconds':analyze(byweek),
        'interpretation':'This result complements rather than replaces retrospective structural higher-order depth. Structural-but-not-yet-executable and executable chains are both preserved as distinct findings.',
        'runway_clock_mutated':False,'permanent_frankie_mutated':False,
    }
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'confirmed':{h:[d for d,z in v['depth'].items() if z['confirmed_all_three_models']] for h,v in result['by_information_horizon_seconds'].items()}},indent=2,sort_keys=True))

if __name__=='__main__': main()
