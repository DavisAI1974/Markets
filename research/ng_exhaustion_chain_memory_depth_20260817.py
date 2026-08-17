#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,json,math
from collections import defaultdict
from pathlib import Path
import numpy as np
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression

EPS=1e-12


def read_events(path):
    out=[]
    with gzip.open(path,'rt') as f:
        for line in f:
            if line.strip():out.append(json.loads(line))
    by=defaultdict(list)
    for e in out:by[e['week_sunday']].append(e)
    for w in by:by[w].sort(key=lambda x:x['t_week_second'])
    if len(by)<3:raise SystemExit(f'need >=3 complete weeks, got {len(by)}')
    return dict(by)
def y_for(e,next_e):return 1 if int(next_e['polarity'])==int(e['polarity']) else 0
def logp(y,p):
    p=min(1-EPS,max(EPS,float(p))); return math.log(p if y else 1-p)
def sample_indices(evs,h):return range(h-1,len(evs)-1)

def fit_fold(by,held,max_depth):
    train_weeks=[w for w in by if w!=held]
    train_states=np.array([e['chain_membership_state']['pre_roll20_oriented_t_minus60_to_t0'] for w in train_weeks for e in by[w]],dtype=float)
    pca=PCA(n_components=.95,svd_solver='full').fit(train_states)
    transformed={}
    for w,evs in by.items():
        curves=np.array([e['chain_membership_state']['pre_roll20_oriented_t_minus60_to_t0'] for e in evs],dtype=float)
        z=pca.transform(curves)
        transformed[w]=[np.r_[z[i],float(evs[i]['polarity'])] for i in range(len(evs))]
    block_dim=len(transformed[held][0]); out={}
    for h in range(1,max_depth+1):
        Xtr=[]; ytr=[]
        for w in train_weeks:
            evs=by[w]; st=transformed[w]
            for j in sample_indices(evs,h):
                Xtr.append(np.concatenate(st[j-h+1:j+1])); ytr.append(y_for(evs[j],evs[j+1]))
        evh=by[held]; sth=transformed[held]; Xte=[]; yte=[]; meta=[]
        for j in sample_indices(evh,h):
            Xte.append(np.concatenate(sth[j-h+1:j+1])); yte.append(y_for(evh[j],evh[j+1]))
            meta.append({'week':held,'current_index':j,'oldest_index':j-h+1,'next_index':j+1})
        Xtr=np.array(Xtr); Xte=np.array(Xte); ytr=np.array(ytr,dtype=int); yte=np.array(yte,dtype=int)
        sc=StandardScaler().fit(Xtr); Xtrs=sc.transform(Xtr); Xtes=sc.transform(Xte)
        full=LogisticRegression(C=1.0,solver='lbfgs',max_iter=2000).fit(Xtrs,ytr)
        pfull=full.predict_proba(Xtes)[:,1]
        if h==1:
            pred=float(ytr.mean()); pred=min(1-EPS,max(EPS,pred)); pred_red=np.full(len(yte),pred)
        else:
            Xtr_red=Xtr[:,block_dim:]; Xte_red=Xte[:,block_dim:]
            scr=StandardScaler().fit(Xtr_red)
            red=LogisticRegression(C=1.0,solver='lbfgs',max_iter=2000).fit(scr.transform(Xtr_red),ytr)
            pred_red=red.predict_proba(scr.transform(Xte_red))[:,1]
        gains=[logp(int(y),pf)-logp(int(y),pr) for y,pf,pr in zip(yte,pfull,pred_red)]
        loss_full=-float(np.mean([logp(int(y),p) for y,p in zip(yte,pfull)]))
        loss_red=-float(np.mean([logp(int(y),p) for y,p in zip(yte,pred_red)]))
        out[h]={'heldout_week':held,'n_train':int(len(ytr)),'n_test':int(len(yte)),'pca_components':int(pca.n_components_),
                'block_dim':int(block_dim),'logloss_full':loss_full,'logloss_reduced':loss_red,'delta_logloss_reduced_minus_full':loss_red-loss_full,
                'accuracy_full':float(np.mean((pfull>=.5)==yte)),'accuracy_reduced':float(np.mean((pred_red>=.5)==yte)),
                'pointwise':[dict(m,actual=int(y),p_full=float(pf),p_reduced=float(pr),gain_nats=float(g)) for m,y,pf,pr,g in zip(meta,yte,pfull,pred_red,gains)]}
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('events'); ap.add_argument('--max-depth',type=int,default=8); ap.add_argument('--out-prefix',default='NG_EXHAUSTION_CHAIN_MEMORY_DEPTH_20260817'); a=ap.parse_args()
    if a.max_depth<1:raise SystemExit('max-depth must be >=1')
    by=read_events(a.events); folds={w:fit_fold(by,w,a.max_depth) for w in sorted(by)}
    aggregate={}
    pointrows=[]
    for h in range(1,a.max_depth+1):
        weekd={w:folds[w][h]['delta_logloss_reduced_minus_full'] for w in folds}
        pts=[p for w in folds for p in folds[w][h]['pointwise']]
        total_n=sum(folds[w][h]['n_test'] for w in folds)
        # Pooled delta is weighted by the common held-out sample count at this depth.
        pooled=sum(folds[w][h]['delta_logloss_reduced_minus_full']*folds[w][h]['n_test'] for w in folds)/total_n
        gains=[p['gain_nats'] for p in pts]
        aggregate[str(h)]={'history_length':h,'pooled_delta_logloss':pooled,'heldout_week_delta_logloss':weekd,
                           'positive_weeks':sum(v>0 for v in weekd.values()),'n_test':total_n,
                           'mean_pointwise_gain_nats':float(np.mean(gains)),'median_pointwise_gain_nats':float(np.median(gains)),
                           'positive_pointwise_fraction':float(np.mean(np.array(gains)>0))}
        for p in pts:pointrows.append(dict(p,history_length=h))
    prefix=0
    for h in range(1,a.max_depth+1):
        x=aggregate[str(h)]
        if x['pooled_delta_logloss']>0 and x['positive_weeks']>=2:prefix=h
        else:break
    deep=aggregate[str(a.max_depth)]
    extend=(deep['pooled_delta_logloss']>0 and deep['positive_weeks']>=2 and a.max_depth<64)
    summary={'status':'RECURSIVE_CHAIN_MEMORY_DEPTH_COMPLETE','weeks':sorted(by),'events_by_week':{w:len(by[w]) for w in by},
             'membership_features':['pre-t0 oriented roll20 curve','raw polarity'],'forbidden_characteristics_used':False,
             'max_depth_tested':a.max_depth,'aggregate':aggregate,'deepest_consecutive_supported_history_length':prefix,
             'adaptive_extension_recommended':extend,'next_max_depth':min(64,a.max_depth*2) if extend else None,
             'interpretation':'history length 1 is second-order next-exhaustion prediction; positive incremental history length 2 is third-order inherited memory; etc.',
             'chain_categories_assigned':False,'price_used':False,'post_t0_used':False,'time_used':False,'family_used':False}
    Path(a.out_prefix+'.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    with gzip.open(a.out_prefix+'_POINTWISE.jsonl.gz','wt') as f:
        for p in pointrows:f.write(json.dumps(p,separators=(',',':'))+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__':main()
