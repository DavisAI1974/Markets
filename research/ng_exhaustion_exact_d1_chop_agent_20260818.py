#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,json,math
from collections import defaultdict
from pathlib import Path

import ng_exhaustion_exact_d1_agents_20260818 as core


def load_event_by_id(*paths):
    out={}
    for p in paths:
        with gzip.open(p,'rt') as f:
            for line in f:
                r=json.loads(line);eid=r.get('event_id');ft=r.get('feature') or {}
                out[eid]={
                  'feature':ft,'state':core.STATE_CODE.get(r.get('seed_state'),'?'),'family':str(r.get('family')),'a_state':str(r.get('a_frozen_post_state')),
                  'h5':core.hval(r,5),'h60':core.hval(r,60),'mfe60':core.hval(r,60,'mfe_ticks'),'mae60':core.hval(r,60,'mae_ticks')
                }
    return out

def predictor(records,events):
    import numpy as np
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder,StandardScaler
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score,brier_score_loss
    num=['peak_abs','pre_prominence','exh_t50_s','exh_t25_s','exh_t10_s','exh_zero_onset_within60_s','roll20_at60','late_flow_pressure_41_60','book_aligned_late_mean','book_aligned_change_from_t0'];cat=['state','family','a_state','pair','duration_family']
    rows=[]
    for r in records:
        e=events.get(r['origin_event_id']);
        if not e:continue
        z={'block':r['block'],'y':1 if r['path_shape_group']=='CHOP_ROTATION' else 0,'pair':r['pair'],'duration_family':r['duration_family'],'state':e['state'],'family':e['family'],'a_state':e['a_state']}
        for k in num:z[k]=e['feature'].get(k)
        rows.append(z)
    tr=[r for r in rows if r['block']=='train'];ytr=np.asarray([r['y'] for r in tr],int)
    if len(tr)<20 or len(set(ytr.tolist()))<2:return {'status':'INSUFFICIENT_TRAIN_VARIATION','train_n':len(tr),'train_chop_n':int(ytr.sum())}
    cols=num+cat;Xtr=[[r.get(k) for k in cols] for r in tr]
    pre=ColumnTransformer([('num',Pipeline([('imp',SimpleImputer(strategy='median')),('sc',StandardScaler())]),list(range(len(num)))),('cat',Pipeline([('imp',SimpleImputer(strategy='most_frequent')),('oh',OneHotEncoder(handle_unknown='ignore'))]),list(range(len(num),len(cols))))])
    pipe=Pipeline([('pre',pre),('clf',LogisticRegression(max_iter=2000,class_weight='balanced',C=1.0))]);pipe.fit(Xtr,ytr)
    out={'status':'TRAIN_FROZEN_CHOP_PREDICTOR','train_n':len(tr),'train_chop_n':int(ytr.sum()),'blocks':{}}
    for b in ('era13','era45','conf'):
        R=[r for r in rows if r['block']==b]
        if not R:continue
        X=[[r.get(k) for k in cols] for r in R];y=np.asarray([r['y'] for r in R],int);p=pipe.predict_proba(X)[:,1];topn=max(1,int(math.ceil(.10*len(R))));order=np.argsort(p)[::-1];top=y[order[:topn]]
        out['blocks'][b]={'n':len(R),'chop_n':int(y.sum()),'base_rate':float(y.mean()),'auc':float(roc_auc_score(y,p)) if len(set(y.tolist()))>1 else None,'brier':float(brier_score_loss(y,p)),'top_decile_n':topn,'top_decile_chop_rate':float(top.mean()),'top_decile_lift':float(top.mean()/y.mean()) if y.mean()>0 else None}
    return out

def ref_return(desc):
    if desc is None or desc['h5'] is None or desc['h60'] is None:return None
    return desc['h60']-desc['h5']
def profit_groups(records,events):
    out=[]
    for key_fields in [('pair',),('duration_family',),('pair','duration_family')]:
        D=defaultdict(list)
        for r in records:
            if r['path_shape_group']!='CHOP_ROTATION':continue
            key='|'.join(f'{k}={r[k]}' for k in key_fields);d=events.get(r['desc_event_id']);v=ref_return(d)
            if v is not None:D[key].append((r,v,d))
        for key,items in D.items():
            tr=[v for r,v,d in items if r['block']=='train']
            if len(tr)<15 or abs(core.mean(tr) or 0)<1e-12:continue
            ori=1 if core.mean(tr)>0 else -1;B={}
            for b in ('train','era13','era45','conf'):
                Q=[(r,v,d) for r,v,d in items if r['block']==b];gross=[ori*v for r,v,d in Q];net05=[x-.5 for x in gross]
                B[b]={'n':len(gross),'gross_mean':core.mean(gross),'gross_median':core.median(gross),'net_0_5_mean':core.mean(net05),'positive_rate':sum(x>0 for x in gross)/len(gross) if gross else None,'mfe60_mean':core.mean([ori*d['mfe60'] for r,v,d in Q if d['mfe60'] is not None]),'mae60_mean':core.mean([ori*d['mae60'] for r,v,d in Q if d['mae60'] is not None])}
            out.append({'grouping':list(key_fields),'candidate':key,'orientation':'WITH_DESCENDANT_POLARITY' if ori==1 else 'AGAINST_DESCENDANT_POLARITY','blocks':B,'guard':'shape membership is realized; execution requires a validated pre-chop predictor or a later causal chop-identification contract'})
    out.sort(key=lambda z:min([z['blocks'][b]['net_0_5_mean'] for b in ('era13','era45','conf') if z['blocks'][b]['net_0_5_mean'] is not None] or [-1e9]),reverse=True)
    return out

def path_groups(records):
    out={}
    for g in ('CHOP_ROTATION','DIRECTIONAL'):
        R=[r for r in records if r['path_shape_group']==g]
        out[g]={'n':len(R),'range_ticks':core.summary([r.get('range_ticks') for r in R]),'mfe_ticks':core.summary([r.get('mfe_ticks') for r in R]),'mae_ticks':core.summary([r.get('mae_ticks') for r in R]),'endpoint_ticks':core.summary([r.get('signed_endpoint_ticks') for r in R]),'path_efficiency':core.summary([r.get('path_efficiency') for r in R]),'two_sidedness':core.summary([r.get('two_sidedness') for r in R])}
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rawpath',required=True);ap.add_argument('--base',required=True);ap.add_argument('--held',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    raw=json.load(open(a.rawpath));assert raw['status']=='EXACT_D1_RAWPATH_AGENT_COMPLETE';records=raw['records'];events=load_event_by_id(a.base,a.held)
    res={'status':'EXACT_D1_CHOP_AGENT_COMPLETE','path_group_summaries':path_groups(records),'pre_chop_predictor':predictor(records,events),'conditional_post_descendant_profit_groups':profit_groups(records,events),'interpretation':'CHOP_ROTATION is a separate potentially profitable opportunity class, not a failed directional leg. Range economics and post-descendant expectancy are reported separately. Intraleg fade/grid rules are not optimized here.','promotion_performed':False,'protected_mutations':{'detector':False,'canonical_rows':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False}}
    Path(a.out).write_text(json.dumps(res,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
