#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import median

TICK=0.001
HORIZONS=(5,10,20,30,60,120,300)
PERSIST=3
MATERIAL_TICKS=2.0
DAY_SECONDS=86400


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
    p=k/n; den=1+z*z/n; ctr=(p+z*z/(2*n))/den
    half=z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return [max(0,ctr-half),min(1,ctr+half)]


def ymd_to_date(s):
    return date(int(s[:4]),int(s[4:6]),int(s[6:8]))


def date_to_ymd(d):
    return d.strftime('%Y%m%d')


def sunday_of(d):
    return d-timedelta(days=(d.weekday()+1)%7)


def parse_day_from_path(path):
    m=re.search(r'(20\d{6})',Path(path).name)
    if not m: raise SystemExit(f'cannot parse YYYYMMDD from {path}')
    return m.group(1)


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


def build_roster(reveal,holdout):
    rows=[]
    for split,arr in (('reveal',reveal),('holdout',holdout)):
        for r in arr:
            pm=post_meta(r); rr60=r.get('dipole_roll60_raw_t_minus60_to_plus60') or []
            pol=int(r['dipole_polarity']); latep=pressure(r)
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


def attach_same_target_day_neighbors(rows):
    byday=defaultdict(list)
    for i,r in enumerate(rows): byday[r['day']].append(i)
    for idxs in byday.values():
        for j,i in enumerate(idxs):
            r=rows[i]
            if j+1<len(idxs):
                n=rows[idxs[j+1]]
                r['literal_next_t0']=n['t0']; r['literal_next_polarity']=n['polarity']
                r['literal_next_same']=int(n['polarity']==r['polarity']); r['literal_next_dt_s']=n['t0']-r['t0']; r['literal_next_split']=n['split']
            else:
                r['literal_next_t0']=r['literal_next_polarity']=r['literal_next_same']=r['literal_next_dt_s']=r['literal_next_split']=None


def summarize_binary(rr,field,success=1):
    vals=[int(r[field]) for r in rr if r.get(field) is not None]
    k=sum(v==success for v in vals); n=len(vals)
    return {'n':n,'hits':k,'rate':None if not n else k/n,'wilson95':wilson(k,n)}


def day_binary(rr,field,success=1):
    return {d:summarize_binary([r for r in rr if r['day']==d],field,success) for d in sorted(set(r['day'] for r in rr))}


def transition_summary(rows,split):
    rr=[r for r in rows if r['split']==split and r.get('literal_next_same') is not None]
    hist={}; byday=defaultdict(list)
    for r in [x for x in rows if x['split']==split]: byday[r['day']].append(r)
    legacy=[]
    for z in byday.values():
        z=sorted(z,key=lambda x:x['t0'])
        for a,b in zip(z,z[1:]): legacy.append({'alive':a['alive_through60'],'same':int(a['polarity']==b['polarity'])})
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
        causal_out[state]={'pooled':summarize_binary(x,'literal_next_same',1),'daily':day_binary(x,'literal_next_same',1),'late_flow_states':{}}
        for fs in ('same','opposite','zero_or_sparse'):
            z=[r for r in x if r['late_flow_state_41_60']==fs]
            causal_out[state]['late_flow_states'][fs]={'pooled':summarize_binary(z,'literal_next_same',1),'daily':day_binary(z,'literal_next_same',1)}
    already=[r for r in rr if r['literal_next_dt_s'] is not None and r['literal_next_dt_s']<=60]
    return {
        'legacy_within_split_reproduction':hist,
        'literal_full_target_day_stream_next_event':literal,
        'causal_asof60_direct_only':causal_out,
        'next_event_already_occurred_by_plus60':{'n':len(already),'fraction_of_eligible':len(already)/len(rr) if rr else None},
        'boundary_note':'Required handoff replication only. Chain ancestry will not reset at target-day boundaries.'
    }


def load_week_stream(raw_paths,target_days):
    paths_by_day={parse_day_from_path(p):p for p in raw_paths}
    target_weeks=sorted(set(sunday_of(ymd_to_date(d)) for d in target_days))
    streams={}
    for ws in target_weeks:
        expected=[date_to_ymd(ws+timedelta(days=i)) for i in range(7)]
        present=[d for d in expected if d in paths_by_day]
        if not present: raise SystemExit(f'no raw files for target week {ws}')
        first=ymd_to_date(present[0]); last=ymd_to_date(present[-1]); nd=(last-first).days+1
        n=nd*DAY_SECONDS
        buy=[0.0]*n; sell=[0.0]*n; raw_price=[float('nan')]*n
        rows=trades=classified=0; actual_trade_indices=[]
        for d in present:
            di=(ymd_to_date(d)-first).days; path=paths_by_day[d]
            with gzip.open(path,'rt') as f:
                for line in f:
                    r=json.loads(line); rows+=1
                    ts=float(r.get('ts_event',r.get('ts',0.0))); sec=int(ts)%DAY_SECONDS; idx=di*DAY_SECONDS+sec
                    if r.get('action')!='T': continue
                    trades+=1
                    px=float(r.get('price',0.0) or 0.0)
                    if px>0:
                        raw_price[idx]=px; actual_trade_indices.append(idx)
                    sz=float(r.get('size',r.get('qty',0.0)) or 0.0)
                    bid0=float(r.get('bid_px_00',0.0) or 0.0); ask0=float(r.get('ask_px_00',0.0) or 0.0)
                    if not (px>0 and sz>0 and bid0>0 and ask0>0 and ask0>=bid0): continue
                    mid=.5*(bid0+ask0)
                    if px>mid: buy[idx]+=sz; classified+=1
                    elif px<mid: sell[idx]+=sz; classified+=1
        if not actual_trade_indices: raise SystemExit(f'no trades in target week {ws}')
        price=[float('nan')]*n; last_px=float('nan')
        for i,v in enumerate(raw_price):
            if finite(v): last_px=float(v)
            price[i]=last_px
        cb=[0.0]*(n+1); cs=[0.0]*(n+1)
        for i in range(n): cb[i+1]=cb[i]+buy[i]; cs[i+1]=cs[i]+sell[i]
        roll=[float('nan')]*n
        for i in range(n):
            lo=max(0,i-19); b=cb[i+1]-cb[lo]; s=cs[i+1]-cs[lo]; z=b+s
            if z>0: roll[i]=(b-s)/z
        streams[date_to_ymd(ws)]={
            'week_sunday':ws,'first_date':first,'last_date':last,'present_days':present,
            'buy':buy,'sell':sell,'price':price,'roll20':roll,
            'first_actual_trade_idx':min(actual_trade_indices),'last_actual_trade_idx':max(actual_trade_indices),
            'rows':rows,'trades':trades,'classified':classified,
        }
    return streams


def event_global_index(stream,day,t0):
    return (ymd_to_date(day)-stream['first_date']).days*DAY_SECONDS+int(t0)


def endpoint(stream,start,pol):
    roll=stream['roll20']; last=None; run=0; first=stream['first_actual_trade_idx']; last_trade=stream['last_actual_trade_idx']
    lo=max(int(start)+1,first)
    for idx in range(lo,last_trade+1):
        v=roll[idx]
        if finite(v): last=float(v)
        if last is None: continue
        run=run+1 if pol*last<=0 else 0
        if run>=PERSIST:
            onset=idx-(PERSIST-1)
            return {'onset_idx':onset,'confirm_idx':idx}
    return None


def price_at(stream,idx):
    if idx<0 or idx>=len(stream['price']): return None
    v=stream['price'][idx]
    return float(v) if finite(v) else None


def first_hits(stream,end,pol):
    p0=price_at(stream,end)
    out={'same_3t_s':None,'opposite_3t_s':None,'same_5t_s':None,'opposite_5t_s':None}
    if p0 is None: return out
    need=set(out); stop=stream['last_actual_trade_idx']
    for idx in range(end+1,stop+1):
        p=price_at(stream,idx)
        if p is None: continue
        d=pol*(p-p0)/TICK
        if 'same_3t_s' in need and d>=3: out['same_3t_s']=idx-end; need.remove('same_3t_s')
        if 'opposite_3t_s' in need and d<=-3: out['opposite_3t_s']=idx-end; need.remove('opposite_3t_s')
        if 'same_5t_s' in need and d>=5: out['same_5t_s']=idx-end; need.remove('same_5t_s')
        if 'opposite_5t_s' in need and d<=-5: out['opposite_5t_s']=idx-end; need.remove('opposite_5t_s')
        if not need: break
    return out


def price_aftermath(stream,end,pol):
    p0=price_at(stream,end); hz={}; last_trade=stream['last_actual_trade_idx']
    if p0 is None: return {'endpoint_price':None,'horizons':hz,'first_hits':first_hits(stream,end,pol)}
    for h in HORIZONS:
        if end+h>last_trade:
            hz[str(h)]={'signed_displacement_ticks':None,'class':None,'mfe_ticks':None,'mae_ticks':None,'censored':True}
            continue
        p=price_at(stream,end+h)
        vals=[price_at(stream,i) for i in range(end,end+h+1)]; vals=[v for v in vals if v is not None]
        if p is None or not vals:
            hz[str(h)]={'signed_displacement_ticks':None,'class':None,'mfe_ticks':None,'mae_ticks':None,'censored':False}
            continue
        signed=pol*(p-p0)/TICK; oriented=[pol*(v-p0)/TICK for v in vals]
        cls='continuation' if signed>=MATERIAL_TICKS else ('reversal' if signed<=-MATERIAL_TICKS else 'chop')
        hz[str(h)]={'signed_displacement_ticks':signed,'class':cls,'mfe_ticks':max(oriented),'mae_ticks':min(oriented),'censored':False}
    return {'endpoint_price':p0,'horizons':hz,'first_hits':first_hits(stream,end,pol)}


def target2_summary(rows,split):
    rr=[r for r in rows if r['split']==split and r.get('endpoint_censored') is False]
    out={'n_with_confirmed_endpoint':len(rr),'n_endpoint_censored':sum(1 for r in rows if r['split']==split and r.get('endpoint_censored')),
         'confirmation_offset_s':{'median':med([r['endpoint_confirm_offset_s'] for r in rr]),'q25':quantile([r['endpoint_confirm_offset_s'] for r in rr],.25),'q75':quantile([r['endpoint_confirm_offset_s'] for r in rr],.75)},
         'structural_onset_offset_s':{'median':med([r['endpoint_onset_offset_s'] for r in rr]),'q25':quantile([r['endpoint_onset_offset_s'] for r in rr],.25),'q75':quantile([r['endpoint_onset_offset_s'] for r in rr],.75)},'horizons':{}}
    for h in HORIZONS:
        valid=[r for r in rr if r['price_aftermath']['horizons'][str(h)]['class'] is not None and not r['price_aftermath']['horizons'][str(h)]['censored']]
        c=Counter(r['price_aftermath']['horizons'][str(h)]['class'] for r in valid)
        disp=[r['price_aftermath']['horizons'][str(h)]['signed_displacement_ticks'] for r in valid]
        out['horizons'][str(h)]={'n':len(valid),'continuation_rate':c['continuation']/len(valid) if valid else None,'reversal_rate':c['reversal']/len(valid) if valid else None,'chop_rate':c['chop']/len(valid) if valid else None,
                                 'signed_displacement_ticks_median':med(disp),'signed_displacement_ticks_q25':quantile(disp,.25),'signed_displacement_ticks_q75':quantile(disp,.75)}
    for label,pred in [('alive_through60',lambda r:r['alive_through60']),('collapsed_by60',lambda r:not r['alive_through60'])]:
        z=[r for r in rr if pred(r)]
        out[label]={'n':len(z),'confirmation_offset_median_s':med([r['endpoint_confirm_offset_s'] for r in z])}
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--reveal-records',required=True); ap.add_argument('--holdout-records',required=True)
    ap.add_argument('--out-prefix',default='NG_EXHAUSTION_AFTERMATH_VALIDATION_V2_20260817')
    ap.add_argument('raw_days',nargs='+')
    a=ap.parse_args()
    reveal=json.load(open(a.reveal_records)); holdout=json.load(open(a.holdout_records))
    if len(reveal)!=1718 or len(holdout)!=1711: raise SystemExit(f'population drift reveal={len(reveal)} holdout={len(holdout)}')
    rows=build_roster(reveal,holdout)
    if len(rows)!=3429: raise SystemExit('combined population drift')
    if len(set((r['day'],r['t0']) for r in rows))!=len(rows): raise SystemExit('duplicate day/t0 event identity')
    attach_same_target_day_neighbors(rows)
    target_days=sorted(set(r['day'] for r in rows)); streams=load_week_stream(a.raw_days,target_days)
    checks=Counter()
    for r in rows:
        ws=date_to_ymd(sunday_of(ymd_to_date(r['day']))); stream=streams[ws]; start=event_global_index(stream,r['day'],r['t0'])
        ep=endpoint(stream,start,r['polarity']); artz=r['zero_within60_s']
        if ep is None:
            r['endpoint_censored']=True; r['endpoint_onset_idx']=r['endpoint_confirm_idx']=None
            r['endpoint_onset_offset_s']=r['endpoint_confirm_offset_s']=None; r['price_aftermath']=None
        else:
            onset=ep['onset_idx']; confirm=ep['confirm_idx']
            r['endpoint_censored']=False; r['endpoint_onset_idx']=onset; r['endpoint_confirm_idx']=confirm
            r['endpoint_onset_offset_s']=onset-start; r['endpoint_confirm_offset_s']=confirm-start
            r['price_aftermath']=price_aftermath(stream,confirm,r['polarity'])
        if artz is not None:
            checks['artifact_zero_present']+=1
            if ep is not None and int(artz)==int(r['endpoint_onset_offset_s']): checks['artifact_zero_onset_exact_match']+=1
            else: checks['artifact_zero_mismatch']+=1
        else:
            checks['artifact_zero_absent']+=1
            if ep is not None and r['endpoint_confirm_offset_s']<=60: checks['unexpected_confirmed_termination_le60']+=1
            if ep is not None and r['endpoint_onset_offset_s']<=60<r['endpoint_confirm_offset_s']: checks['onset_by60_confirmation_after60']+=1
    if checks['artifact_zero_mismatch'] or checks['unexpected_confirmed_termination_le60']:
        raise SystemExit(f'endpoint reconstruction drift {dict(checks)}')

    summary={
      'status':'CAUSAL_AFTERMATH_VALIDATION_V2_COMPLETE',
      'population':{'reveal':len(reveal),'holdout':len(holdout),'combined':len(rows),'target_days':target_days},
      'raw_week_streams':{k:{x:v[x] for x in ('present_days','rows','trades','classified','first_actual_trade_idx','last_actual_trade_idx')} for k,v in streams.items()},
      'endpoint_policy':{'hardcoded_end':False,'termination':'three consecutive causal forward-filled oriented roll20 <= 0','structural_onset':'first second of qualifying run','causal_confirmation':'third second of qualifying run','primary_aftermath_anchor':'causal confirmation second','plus60_is_endpoint':False,'calendar_midnight_censors':False},
      'endpoint_reconstruction_checks':dict(checks),
      'target1':{'scope':'required frozen target-day replication before week-continuous chain study','reveal':transition_summary(rows,'reveal'),'holdout':transition_summary(rows,'holdout')},
      'target2':{'scope':'dynamic endpoint price aftermath on continuous target-week raw streams','reveal':target2_summary(rows,'reveal'),'holdout':target2_summary(rows,'holdout')},
      'no_runway_clock_mutation':True,'permanent_frankie_mutated':False,
    }
    clean=[]
    for r in rows:
        clean.append({
          'identity':{'split':r['split'],'source_id':r['source_id'],'day':r['day'],'t0_second_utc':r['t0'],'polarity':r['polarity'],'family':r['family']},
          'features_asof_plus60':{'alive_through60':r['alive_through60'],'zero_within60_s':r['zero_within60_s'],'late_flow_pressure_41_60':r['late_flow_pressure_41_60'],'late_flow_state_41_60':r['late_flow_state_41_60'],'roll20_at60':r['roll20_at60'],'roll60_aligned_at60':r['roll60_aligned_at60'],'book_aligned_late_mean':r['book_aligned_late_mean'],'book_aligned_change_from_t0_window':r['book_aligned_change_from_t0_window']},
          'dynamic_endpoint':{'structural_onset_offset_s':r['endpoint_onset_offset_s'],'causal_confirmation_offset_s':r['endpoint_confirm_offset_s'],'censored':r['endpoint_censored']},
          'outcome_target1':{'literal_next_t0':r['literal_next_t0'],'literal_next_polarity':r['literal_next_polarity'],'literal_next_same':r['literal_next_same'],'literal_next_dt_s':r['literal_next_dt_s'],'literal_next_split':r['literal_next_split'],'direct_asof60_eligible':r['literal_next_dt_s'] is not None and r['literal_next_dt_s']>60},
          'outcome_target2':r['price_aftermath']
        })
    with gzip.open(a.out_prefix+'_EVENT_TABLE.jsonl.gz','wt') as f:
        for r in clean: f.write(json.dumps(r,separators=(',',':'))+'\n')
    Path(a.out_prefix+'.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=='__main__': main()
