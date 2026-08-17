#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,json,math
from collections import Counter,defaultdict
from pathlib import Path


def finite(x):
    try:return math.isfinite(float(x))
    except Exception:return False

def quantile(xs,q):
    a=sorted(float(x) for x in xs if finite(x))
    if not a:return None
    if len(a)==1:return a[0]
    z=q*(len(a)-1); i=int(math.floor(z)); j=min(i+1,len(a)-1); w=z-i
    return a[i]*(1-w)+a[j]*w

def wilson(k,n,z=1.959963984540054):
    if n<=0:return [None,None]
    p=k/n; den=1+z*z/n; ctr=(p+z*z/(2*n))/den; half=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [max(0,ctr-half),min(1,ctr+half)]
def binary(rr):
    vals=[int(r['next_same']) for r in rr if r.get('next_same') is not None]; n=len(vals); k=sum(vals)
    return {'n':n,'same_hits':k,'same_rate':k/n if n else None,'flip_rate':(n-k)/n if n else None,'wilson95_same':wilson(k,n)}
def by_day(rr):
    return {d:binary([r for r in rr if r['day']==d]) for d in sorted(set(r['day'] for r in rr))}
def edges(rr,key,qs):return [quantile([r[key] for r in rr if finite(r.get(key))],q) for q in qs]
def bindex(v,ed):
    if not finite(v):return None
    for i,e in enumerate(ed):
        if float(v)<=float(e):return i
    return len(ed)
def bins(rr,key,ed):
    out=[]
    for i in range(len(ed)+1):
        z=[r for r in rr if bindex(r.get(key),ed)==i]
        out.append({'bin':i,'n':len(z),'feature_median':quantile([r.get(key) for r in z],.5),'same':binary(z),'daily':by_day(z)})
    return out
def tertile2d(rr,key1,e1,key2,e2):
    out=[]
    for i in range(3):
        for j in range(3):
            z=[r for r in rr if bindex(r.get(key1),e1)==i and bindex(r.get(key2),e2)==j]
            out.append({'bin1':i,'bin2':j,'n':len(z),'same':binary(z)})
    return out
def adjacent_monotone(table):
    rates=[x['same']['same_rate'] for x in table if x['same']['n']>0]
    if len(rates)<2:return None
    return {'nondecreasing_pairs':sum(b>=a for a,b in zip(rates,rates[1:])),'adjacent_pairs':len(rates)-1,'rates':rates}

def load(path):
    out=[]
    with gzip.open(path,'rt') as f:
        for line in f:
            e=json.loads(line); i=e['identity']; ft=e['features_asof_plus60']; o=e['outcome_target1']
            out.append({'split':i['split'],'day':i['day'],'family':i['family'],'polarity':i['polarity'],'alive':bool(ft['alive_through60']),
                        'pressure':ft['late_flow_pressure_41_60'],'flow_state':ft['late_flow_state_41_60'],'roll20':ft['roll20_at60'],
                        'book':ft['book_aligned_late_mean'],'book_change':ft['book_aligned_change_from_t0_window'],
                        'next_same':o['literal_next_same'],'next_dt':o['literal_next_dt_s'],'eligible60':bool(o['direct_asof60_eligible'])})
    if len(out)!=3429:raise SystemExit(f'population drift {len(out)}')
    return out

def split_analysis(allrows,split,freezes):
    raw=[r for r in allrows if r['split']==split and r['next_same'] is not None]
    rr=[r for r in raw if r['eligible60']]
    out={'literal_next_exists_n':len(raw),'direct_asof60_n':len(rr),'already_realized_by_plus60_n':sum(not r['eligible60'] for r in raw),
         'already_realized_fraction':sum(not r['eligible60'] for r in raw)/len(raw) if raw else None,'baseline':{},'late_flow_sign':{},
         'quintiles':{},'two_dimensional':{},'family_descriptive':{}}
    for alive,label in ((True,'alive_through60'),(False,'collapsed_by60')):
        z=[r for r in rr if r['alive']==alive]
        out['baseline'][label]={'pooled':binary(z),'daily':by_day(z)}
        out['late_flow_sign'][label]={}
        for state in ('same','opposite','zero_or_sparse'):
            q=[r for r in z if r['flow_state']==state]
            out['late_flow_sign'][label][state]={'pooled':binary(q),'daily':by_day(q)}
        for key in ('pressure','roll20'):
            ed=freezes[label][key]
            tab=bins(z,key,ed)
            out['quintiles'][f'{label}_{key}']={'edges_from_reveal':ed,'bins':tab,'monotone':adjacent_monotone(tab)}
    z=[r for r in rr if not r['alive']]
    pe3=freezes['collapsed_by60']['pressure_tertiles']; be3=freezes['collapsed_by60']['book_tertiles']; re3=freezes['collapsed_by60']['roll20_tertiles']
    out['two_dimensional']['collapsed_pressure_x_book']={'pressure_edges_from_reveal':pe3,'book_edges_from_reveal':be3,'cells':tertile2d(z,'pressure',pe3,'book',be3)}
    out['two_dimensional']['collapsed_pressure_x_roll20']={'pressure_edges_from_reveal':pe3,'roll20_edges_from_reveal':re3,'cells':tertile2d(z,'pressure',pe3,'roll20',re3)}
    for fam in ('A','B','C'):
        q=[r for r in rr if r['family']==fam]
        out['family_descriptive'][fam]={'n':len(q),'alive':binary([r for r in q if r['alive']]),'collapsed':binary([r for r in q if not r['alive']])}
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('event_table'); ap.add_argument('--out',default='NG_EXHAUSTION_TARGET1_TRANSITION_VALIDATION_20260817.json'); a=ap.parse_args()
    rows=load(a.event_table); reveal=[r for r in rows if r['split']=='reveal' and r['eligible60'] and r['next_same'] is not None]
    freezes={}
    for alive,label in ((True,'alive_through60'),(False,'collapsed_by60')):
        z=[r for r in reveal if r['alive']==alive]
        freezes[label]={'pressure':edges(z,'pressure',(.2,.4,.6,.8)),'roll20':edges(z,'roll20',(.2,.4,.6,.8))}
    z=[r for r in reveal if not r['alive']]
    freezes['collapsed_by60']['pressure_tertiles']=edges(z,'pressure',(1/3,2/3))
    freezes['collapsed_by60']['book_tertiles']=edges(z,'book',(1/3,2/3))
    freezes['collapsed_by60']['roll20_tertiles']=edges(z,'roll20',(1/3,2/3))
    out={'status':'CAUSAL_TARGET1_TRANSITION_VALIDATION_COMPLETE','population':{'combined':len(rows)},'feature_asof_s':60,
         'outcome':'literal next detected exhaustion on same frozen target date','causal_eligibility':'literal next t0 must be > anchor t0+60',
         'reveal_derived_freezes':freezes,'reveal':split_analysis(rows,'reveal',freezes),'holdout':split_analysis(rows,'holdout',freezes),
         'interpretation_guardrail':'Required four-target-date replication only. Later chain study uses complete week-continuous event ancestry and does not reset at date boundaries.',
         'no_holdout_retuning':True,'no_runway_clock_mutation':True,'permanent_frankie_mutated':False}
    Path(a.out).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__':main()
