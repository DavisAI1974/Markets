#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import ng_exhaustion_exact_d1_agents_v2_20260818 as core

NUM = [
    'peak_abs','pre_prominence','exh_t50_s','exh_t25_s','exh_t10_s',
    'exh_zero_onset_within60_s','roll20_at60','late_flow_pressure_41_60',
    'book_aligned_late_mean','book_aligned_change_from_t0_window',
]
CAT = ['state','family','a_state']


def event_rows(base, held, weeks, long_keys):
    out=[]
    for path in (base, held):
        with gzip.open(path,'rt') as f:
            for line in f:
                r=json.loads(line); w=r['week_sunday']; b=core.d1_block_for(w,weeks)
                if b=='prelineage_unlabeled':
                    continue
                ft=r.get('feature') or {}
                z={
                    'week':w,'block':b,'y':1 if (w,int(r['sequence_index'])) in long_keys else 0,
                    'state':str(r.get('seed_state')),'family':str(r.get('family')),
                    'a_state':str(r.get('a_frozen_post_state')),
                }
                for k in NUM:
                    z[k]=ft.get(k)
                out.append(z)
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base',required=True); ap.add_argument('--held',required=True)
    ap.add_argument('--base-lineage',required=True); ap.add_argument('--held-lineage',required=True)
    ap.add_argument('--summary',required=True); ap.add_argument('--out',required=True)
    a=ap.parse_args()

    weeks=json.load(open(a.summary))['weeks']
    events=core.load_events(a.base,a.held); lineage=core.load_lineage(a.base_lineage,a.held_lineage)
    d1,model=core.d1_records(events,lineage,weeks); long_label=model['labels'][-1]
    long_keys={(r['week'],r['origin_seq']) for r in d1 if r['duration_family']==long_label}
    rows=event_rows(a.base,a.held,weeks,long_keys)

    cols=NUM+CAT
    tr=[r for r in rows if r['block']=='train']
    Xtr=[[r.get(k) for k in cols] for r in tr]; ytr=np.asarray([r['y'] for r in tr],int)
    pre=ColumnTransformer([
        ('num',Pipeline([('imp',SimpleImputer(strategy='median')),('sc',StandardScaler())]),list(range(len(NUM)))),
        ('cat',Pipeline([('imp',SimpleImputer(strategy='most_frequent')),('oh',OneHotEncoder(handle_unknown='ignore'))]),list(range(len(NUM),len(cols)))),
    ])
    pipe=Pipeline([('pre',pre),('clf',LogisticRegression(max_iter=3000,class_weight='balanced',C=1.0))])
    pipe.fit(Xtr,ytr)

    result={
        'status':'EXACT_D1_PRELONG_PREDICTOR_V2_COMPLETE',
        'target':'train-frozen long exact-D1 membership vs all causally eligible origins',
        'long_family':long_label,
        'train_n':len(tr),'train_positive':int(ytr.sum()),'blocks':{},
        'feature_fix':'uses canonical book_aligned_change_from_t0_window field',
        'preserve_all_policy':True,
        'guard':'prediction ranks probability only; no D1 row is removed and realized duration is never used as an origin-time input',
        'promotion_performed':False,
        'protected_mutations':{'detector':False,'canonical_rows':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False},
    }
    for b in ('era45','conf','held'):
        R=[r for r in rows if r['block']==b]
        X=[[r.get(k) for k in cols] for r in R]; y=np.asarray([r['y'] for r in R],int)
        p=pipe.predict_proba(X)[:,1]; order=np.argsort(p)[::-1]; topn=max(1,int(math.ceil(.10*len(R)))); top=y[order[:topn]]
        result['blocks'][b]={
            'n':len(R),'positives':int(y.sum()),'base_rate':float(y.mean()),
            'auc':float(roc_auc_score(y,p)) if len(set(y.tolist()))>1 else None,
            'average_precision':float(average_precision_score(y,p)),
            'brier':float(brier_score_loss(y,p)),
            'top_decile_n':topn,'top_decile_positive_rate':float(top.mean()),
            'top_decile_lift':float(top.mean()/y.mean()) if y.mean()>0 else None,
        }
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')


if __name__=='__main__':
    main()
