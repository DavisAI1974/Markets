#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from ng_dipole_native_shape_audit import flow_series
from ng_dipole_runway_audit import TICK, load_day

HORIZONS=(5,10,20,30,60,120,300)
PERSIST=3
MATERIAL_TICKS=2.0


def finite(x):
    try: return math.isfinite(float(x))
    except Exception: return False


def mean(xs):
    a=[float(x) for x in xs if finite(x)]
    return sum(a)/len(a) if a else None


def med(xs):
    a=[float(x) for x in xs if finite(x)]
    return float(median(a)) if a else None


def quantile(xs,q):
    a=sorted(float(x) for x in xs if finite(x))
    if not a: return None
    if len(a)==1: return a[0]
    z=q*(len(a)-1); i=int(math.floor(z)); j=min(i+1,len(a)-1); w=z-i
    return a[i]*(1-w)+a[j]*w


def wilson(k,n,z=1.959963984540054):
    if n<=0: return [None,None]
    p=k/n; den=1+z*z/n; ctr=(p+z*z/(2*n))/den; half=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [max(0,ctr-half),min(1,ctr+half)]


def pressure(r,lo=101,hi=121):
    pol=int(r['dipole_polarity'])
    b=sum(float(x or 0) for x in r['aggressor_buy_volume_t_minus60_to_plus60'][lo:hi])
    s=sum(float(x or 0) for x in r['aggressor_sell_volume_t_minus60_to_plus60'][lo:hi])
    aligned=b if pol>0 else s; opposite=s if pol>0 else b; tot=aligned+opposite
    return None if tot<=0 else (aligned-opposite)/tot


def pressure_state(v):
    if v is None or abs(float(v))<1e-12: return 'zero_or_sparse'
    return 'same' if float(v)>0 else 'opposite'


def post_meta(r):
    return r.get('post_exhaustion') or r.get('post_exhaustion_dipole_only') or {}


def artifact_id(r,split):
    return r.get('event_id') if split=='reveal' else r.get('blind_id')


def full_endpoint(flow,t0,pol):
    last=None; run=0
    for sec in range(int(t0),len(flow)):
        v=flow[sec]
        if finite(v): last=float(v)
        if sec<=t0 or last is None: continue
        oriented=pol*last
        run = run+1 if oriented<=0 else 0
        if run>=PERSIST:
            return sec-(PERSIST-1)
    return None


def price_at(day,sec):
    if sec<0 or sec>=len(day.price): return None
    v=day.price[sec]
    return float(v) if finite(v) else None


def first_hits(day,end,pol):
    p0=price_at(day,end)
    out={'same_3t_s':None,'opposite_3t_s':None,'same_5t_s':None,'opposite_5t_s':None}
    if p0 is None: return out
    need=set(out)
    for sec in range(end+1,len(day.price)):
        p=price_at(day,sec)
        if p is None: continue
        d=pol*(p-p0)/TICK
        if 'same_3t_s' in need and d>=3: out['same_3t_s']=sec-end; need.remove('same_3t_s')
        if 'opposite_3t_s' in need and d<=-3: out['opposite_3t_s']=sec-end; need.remove('opposite_3t_s')
        if 'same_5t_s' in need and d>=5: out['same_5t_s']=sec-end; need.remove('same_5t_s')
        if 'opposite_5t_s' in need and d<=-5: out['opposite_5t_s']=sec-end; need.remove('opposite_5t_s')
        if not need: break
    return out


def price_aftermath(day,end,pol):
    p0=price_at(day,end)
    if p0 is None: return {'endpoint_price':None,'horizons':{},'first_hits':first_hits(day,end,pol)}
    hz={}
    for h in HORIZONS:
        stop=min(len(day.price)-1,end+h)
        p=price_at(day,stop)
        vals=[price_at(day,s) for s in range(end,stop+1)]
        vals=[v for v in vals if v is not None]
        if p is None or not vals:
            hz[str(h)]={'signed_displacement_ticks':None,'class':None,'mfe_ticks':None,'mae_ticks':None,'censored':stop<end+h}
            continue
        signed=pol*(p-p0)/TICK
        oriented=[pol*(v-p0)/TICK for v in vals]
        cls='continuation' if signed>=MATERIAL_TICKS else ('reversal' if signed<=-MATERIAL_TICKS else 'chop')
        hz[str(h)]={'signed_displacement_ticks':signed,'class':cls,'mfe_ticks':max(oriented),'mae_ticks':min(oriented),'censored':stop<end+h}
    return {'endpoint_price':p0,'horizons':hz,'first_hits':first_hits(day,end,pol)}


def build_roster(reveal,holdout):
    rows=[]
    for split,arr in (('reveal',reveal),('holdout',holdout)):
        for r in arr:
            pm=post_meta(r); rr60=r.get('dipole_roll60_raw_t_minus60_to_plus60') or []
            pol=int(r['dipole_polarity'])
            latep=pressure(r)
            book=r.get('book_10level_imbalance_t_minus60_to_plus60') or []
            late_book=[float(v) for v in book[101:121] if finite(v)]
            t0_book=[float(v) for v in book[41:61] if finite(v)]
            row={
                'split':split,'source_id':artifact_id(r,split),'day':str(r['day']),'t0':int(r['t0_second_utc']),
                'polarity':pol,'family':str(r['family']),'zero_within60_s':pm.get('zero_s'),
                'alive_through60':pm.get('zero_s') is None,'late_flow_pressure_41_60':latep,
                'late_flow_state_41_60':pressure_state(latep),
                'roll20_at60':float(r['dipole_roll20_oriented_t_minus60_to_plus60'][120]),
                'roll60_aligned_at60':None if len(rr60)<121 or not finite(rr60[120]) else pol*float(rr60[120]),
                'book_aligned_late_mean':None if not late_book else pol*sum(late_book)/len(late_book),
                'book_aligned_change_from_t0_window':None,
            }
            if late_book and t0_book:
                row['book_aligned_change_from_t0_window']=pol*(sum(late_book)/len(late_book)-sum(t0_book)/len(t0_book))
            rows.append(row)
    rows.sort(key=lambda x:(x['day'],x['t0']))
    return rows


def attach_neighbors(rows):
    byday=defaultdict(list)
    for i,r in enumerate(rows): byday[r['day']].append(i)
    for idxs in byday.values():
        for j,i in enumerate(idxs):
            r=rows[i]
            if j+1<len(idxs):
                n=rows[idxs[j+1]]; r['literal_next_t0']=n['t0']; r['literal_next_polarity']=n['polarity']; r['literal_next_same']=int(n['polarity']==r['polarity']); r['literal_next_dt_s']=n['t0']-r['t0']; r['literal_next_split']=n['split']
            else:
                r['literal_next_t0']=r['literal_next_polarity']=r['literal_next_same']=r['literal_next_dt_s']=r['literal_next_split']=None


def next_after(rows,byday_idx,current_i,after_t):
    idxs=byday_idx[rows[current_i]['day']]
    pos=idxs.index(current_i)
    for ii in idxs[pos+1:]:
        if rows[ii]['t0']>after_t: return rows[ii]
    return None


def summarize_binary(rr,field,success=1):
    vals=[int(r[field]) for r in rr if r.get(field) is not None]
    k=sum(v==success for v in vals); n=len(vals)
    return {'n':n,'hits':k,'rate':None if not n else k/n,'wilson95':wilson(k,n)}


def day_binary(rr,field,success=1):
    out={}
    for d in sorted(set(r['day'] for r in rr)):
        out[d]=summarize_binary([r for r in rr if r['day']==d],field,success)
    return out


def transition_summary(rows,split):
    rr=[r for r in rows if r['split']==split and r.get('literal_next_same') is not None]
    hist={}
    byday=defaultdict(list)
    for r in [x for x in rows if x['split']==split]: byday[r['day']].append(r)
    legacy=[]
    for d,z in byday.items():
        z=sorted(z,key=lambda x:x['t0'])
        for a,b in zip(z,z[1:]): legacy.append({'day':d,'alive':a['alive_through60'],'same':int(a['polarity']==b['polarity'])})
    for state,val in [('alive',True),('collapsed',False)]:
        x=[q for q in legacy if q['alive']==val]; k=sum(q['same'] for q in x)
        hist[state]={'n':len(x),'same_hits':k,'same_rate':k/len(x) if x else None,'wilson95':wilson(k,len(x))}

    literal={}
    for state,val in [('alive',True),('collapsed',False)]:
        x=[r for r in rr if r['alive_through60']==val]
        literal[state]={'pooled':summarize_binary(x,'literal_next_same',1),'daily':day_binary(x,'literal_next_same',1)}

    causal=[r for r in rr if r['literal_next_dt_s'] is not None and r['literal_next_dt_s']>60]
    causal_out={}
    for state,val in [('alive',True),('collapsed',False)]:
        x=[r for r in causal if r['alive_through60']==val]
        causal_out[state]={'pooled':summarize_binary(x,'literal_next_same',1),'daily':day_binary(x,'literal_next_same',1)}
        causal_out[state]['late_flow_states']={}
        for fs in ('same','opposite','zero_or_sparse'):
            z=[r for r in x if r['late_flow_state_41_60']==fs]
            causal_out[state]['late_flow_states'][fs]={'pooled':summarize_binary(z,'literal_next_same',1),'daily':day_binary(z,'literal_next_same',1)}
    already=[r for r in rr if r['literal_next_dt_s'] is not None and r['literal_next_dt_s']<=60]
    return {'legacy_within_split_reproduction':hist,'literal_full_stream_next_event':literal,'causal_asof60_direct_only':causal_out,
            'next_event_already_occurred_by_plus60':{'n':len(already),'fraction_of_eligible':len(already)/len(rr) if rr else None}}


def target2_summary(rows,split):
    rr=[r for r in rows if r['split']==split and r.get('endpoint_censored') is False]
    out={'n_with_endpoint':len(rr),'n_endpoint_censored':sum(1 for r in rows if r['split']==split and r.get('endpoint_censored')),
         'endpoint_offset_s':{'median':med([r['endpoint_offset_s'] for r in rr]),'q25':quantile([r['endpoint_offset_s'] for r in rr],.25),'q75':quantile([r['endpoint_offset_s'] for r in rr],.75)},'horizons':{}}
    for h in HORIZONS:
        valid=[r for r in rr if r['price_aftermath']['horizons'][str(h)]['class'] is not None and not r['price_aftermath']['horizons'][str(h)]['censored']]
        c=Counter(r['price_aftermath']['horizons'][str(h)]['class'] for r in valid)
        disp=[r['price_aftermath']['horizons'][str(h)]['signed_displacement_ticks'] for r in valid]
        out['horizons'][str(h)]={'n':len(valid),'continuation_rate':c['continuation']/len(valid) if valid else None,'reversal_rate':c['reversal']/len(valid) if valid else None,'chop_rate':c['chop']/len(valid) if valid else None,
                                 'signed_displacement_ticks_median':med(disp),'signed_displacement_ticks_q25':quantile(disp,.25),'signed_displacement_ticks_q75':quantile(disp,.75)}
    for label,pred in [('alive_through60',lambda r:r['alive_through60']),('collapsed_by60',lambda r:not r['alive_through60'])]:
        z=[r for r in rr if pred(r)]; out[label]={'n':len(z),'endpoint_offset_median_s':med([r['endpoint_offset_s'] for r in z])}
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--reveal-records',required=True); ap.add_argument('--holdout-records',required=True); ap.add_argument('raw_days',nargs='+')
    ap.add_argument('--out-prefix',default='NG_EXHAUSTION_AFTERMATH_VALIDATION_20260817')
    a=ap.parse_args()
    reveal=json.load(open(a.reveal_records)); holdout=json.load(open(a.holdout_records))
    if len(reveal)!=1718 or len(holdout)!=1711: raise SystemExit(f'population drift reveal={len(reveal)} holdout={len(holdout)}')
    rows=build_roster(reveal,holdout)
    if len(rows)!=3429: raise SystemExit('combined population drift')
    keys=[(r['day'],r['t0']) for r in rows]
    if len(set(keys))!=len(keys): raise SystemExit('duplicate day/t0 event identity')
    attach_neighbors(rows)
    days={}; flows={}
    for p in a.raw_days:
        d=load_day(p); days[d.day]=d; flows[d.day]=flow_series(d,20)
    if set(days)!=set(r['day'] for r in rows): raise SystemExit(f'raw day mismatch {sorted(days)} vs {sorted(set(r["day"] for r in rows))}')
    byday_idx=defaultdict(list)
    for i,r in enumerate(rows): byday_idx[r['day']].append(i)
    zero_checks=Counter()
    for i,r in enumerate(rows):
        flow=flows[r['day']]; day=days[r['day']]; end=full_endpoint(flow,r['t0'],r['polarity'])
        r['endpoint_second_utc']=end; r['endpoint_censored']=end is None; r['endpoint_offset_s']=None if end is None else end-r['t0']
        artz=r['zero_within60_s']
        if artz is not None:
            zero_checks['artifact_zero_present']+=1
            if end is not None and int(artz)==int(end-r['t0']): zero_checks['artifact_zero_exact_match']+=1
            else: zero_checks['artifact_zero_mismatch']+=1
        else:
            zero_checks['artifact_zero_absent']+=1
            if end is not None and end-r['t0']<=60: zero_checks['unexpected_extended_zero_le60']+=1
        if end is None:
            r['events_starting_before_endpoint']=None; r['next_after_endpoint_t0']=None; r['next_after_endpoint_same']=None; r['price_aftermath']=None
        else:
            idxs=byday_idx[r['day']]; pos=idxs.index(i); overlaps=[rows[j] for j in idxs[pos+1:] if rows[j]['t0']<=end]
            r['events_starting_before_endpoint']=len(overlaps)
            nxt=next_after(rows,byday_idx,i,end)
            r['next_after_endpoint_t0']=None if nxt is None else nxt['t0']; r['next_after_endpoint_same']=None if nxt is None else int(nxt['polarity']==r['polarity'])
            r['price_aftermath']=price_aftermath(day,end,r['polarity'])
        n60=next_after(rows,byday_idx,i,r['t0']+60)
        r['next_after_plus60_t0']=None if n60 is None else n60['t0']; r['next_after_plus60_same']=None if n60 is None else int(n60['polarity']==r['polarity'])
    if zero_checks['artifact_zero_mismatch'] or zero_checks['unexpected_extended_zero_le60']:
        raise SystemExit(f'endpoint reconstruction drift {dict(zero_checks)}')

    summary={
      'status':'CAUSAL_AFTERMATH_VALIDATION_COMPLETE',
      'population':{'reveal':len(reveal),'holdout':len(holdout),'combined':len(rows),'days':sorted(days)},
      'endpoint_policy':{'hardcoded_end':False,'termination':'first three consecutive causal forward-filled oriented roll20 <= 0 after t0','session_end_censoring':True,'plus60_is_endpoint':False},
      'endpoint_reconstruction_checks':dict(zero_checks),
      'target1':{'reveal':transition_summary(rows,'reveal'),'holdout':transition_summary(rows,'holdout')},
      'target2':{'reveal':target2_summary(rows,'reveal'),'holdout':target2_summary(rows,'holdout')},
      'overlap_topology':{},
      'no_runway_clock_mutation':True,'permanent_frankie_mutated':False,
    }
    for split in ('reveal','holdout'):
        z=[r for r in rows if r['split']==split and not r['endpoint_censored']]
        counts=Counter(r['events_starting_before_endpoint'] for r in z)
        summary['overlap_topology'][split]={'n':len(z),'with_any_intervening_event_before_endpoint':sum(v for k,v in counts.items() if k>0),
          'fraction_with_any_intervening_event_before_endpoint':sum(v for k,v in counts.items() if k>0)/len(z) if z else None,
          'count_distribution':{str(k):v for k,v in sorted(counts.items())}}

    clean=[]
    for r in rows:
        clean.append({
          'identity':{'split':r['split'],'source_id':r['source_id'],'day':r['day'],'t0_second_utc':r['t0'],'polarity':r['polarity'],'family':r['family']},
          'features_asof_plus60':{'alive_through60':r['alive_through60'],'zero_within60_s':r['zero_within60_s'],'late_flow_pressure_41_60':r['late_flow_pressure_41_60'],'late_flow_state_41_60':r['late_flow_state_41_60'],'roll20_at60':r['roll20_at60'],'roll60_aligned_at60':r['roll60_aligned_at60'],'book_aligned_late_mean':r['book_aligned_late_mean'],'book_aligned_change_from_t0_window':r['book_aligned_change_from_t0_window']},
          'dynamic_endpoint':{'second_utc':r['endpoint_second_utc'],'offset_s':r['endpoint_offset_s'],'censored':r['endpoint_censored'],'events_starting_before_endpoint':r['events_starting_before_endpoint']},
          'outcome_target1':{'literal_next_t0':r['literal_next_t0'],'literal_next_polarity':r['literal_next_polarity'],'literal_next_same':r['literal_next_same'],'literal_next_dt_s':r['literal_next_dt_s'],'literal_next_split':r['literal_next_split'],'direct_asof60_eligible':r['literal_next_dt_s'] is not None and r['literal_next_dt_s']>60,'next_after_plus60_t0':r['next_after_plus60_t0'],'next_after_plus60_same':r['next_after_plus60_same'],'next_after_endpoint_t0':r['next_after_endpoint_t0'],'next_after_endpoint_same':r['next_after_endpoint_same']},
          'outcome_target2':r['price_aftermath']
        })
    with gzip.open(a.out_prefix+'_EVENT_TABLE.jsonl.gz','wt') as f:
        for r in clean: f.write(json.dumps(r,separators=(',',':'))+'\n')
    Path(a.out_prefix+'.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=='__main__': main()
