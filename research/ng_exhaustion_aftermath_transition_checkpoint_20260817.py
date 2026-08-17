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
DAY_SECONDS=86400
CHECKPOINT=20
HORIZONS=(20,60,120,300)
MATERIAL_TICKS=2.0


def finite(x):
    try: return math.isfinite(float(x))
    except Exception: return False


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


def ymd(s): return date(int(s[:4]),int(s[4:6]),int(s[6:8]))
def ymds(d): return d.strftime('%Y%m%d')
def sunday_of(d): return d-timedelta(days=(d.weekday()+1)%7)

def parse_day(path):
    m=re.search(r'(20\d{6})',Path(path).name)
    if not m: raise SystemExit(f'cannot parse date from {path}')
    return m.group(1)


def load_v2_event_table(path):
    rows=[]
    with gzip.open(path,'rt') as f:
        for line in f:
            if line.strip(): rows.append(json.loads(line))
    if len(rows)!=3429: raise SystemExit(f'V2 event population drift {len(rows)}')
    return rows


def load_week_streams(raw_paths,target_days):
    pby={parse_day(p):p for p in raw_paths}
    weeks=sorted(set(sunday_of(ymd(d)) for d in target_days))
    out={}
    for ws in weeks:
        expected=[ymds(ws+timedelta(days=i)) for i in range(6)] # Sunday through Friday
        missing=[d for d in expected if d not in pby]
        if missing: raise SystemExit(f'missing continuous week files for {ymds(ws)}: {missing}')
        first=ws; n=6*DAY_SECONDS
        buy=[0.0]*n; sell=[0.0]*n; raw_price=[float('nan')]*n; raw_book=[float('nan')]*n
        actual_trades=[]; rows=trades=classified=book_rows=0
        for d in expected:
            di=(ymd(d)-first).days
            with gzip.open(pby[d],'rt') as f:
                for line in f:
                    r=json.loads(line); rows+=1
                    ts=float(r.get('ts_event',r.get('ts',0.0))); sec=int(ts)%DAY_SECONDS; idx=di*DAY_SECONDS+sec
                    bid_sz=sum(float(r.get(f'bid_sz_{j:02d}',0.0) or 0.0) for j in range(10))
                    ask_sz=sum(float(r.get(f'ask_sz_{j:02d}',0.0) or 0.0) for j in range(10))
                    tot=bid_sz+ask_sz
                    if tot>0:
                        raw_book[idx]=(bid_sz-ask_sz)/tot; book_rows+=1
                    if r.get('action')!='T': continue
                    trades+=1
                    px=float(r.get('price',0.0) or 0.0)
                    if px>0: raw_price[idx]=px; actual_trades.append(idx)
                    sz=float(r.get('size',r.get('qty',0.0)) or 0.0)
                    bid0=float(r.get('bid_px_00',0.0) or 0.0); ask0=float(r.get('ask_px_00',0.0) or 0.0)
                    if not (px>0 and sz>0 and bid0>0 and ask0>0 and ask0>=bid0): continue
                    mid=.5*(bid0+ask0)
                    if px>mid: buy[idx]+=sz; classified+=1
                    elif px<mid: sell[idx]+=sz; classified+=1
        if not actual_trades: raise SystemExit(f'no actual trades in week {ymds(ws)}')
        price=[float('nan')]*n; book=[float('nan')]*n; lp=lb=float('nan')
        for i in range(n):
            if finite(raw_price[i]): lp=float(raw_price[i])
            if finite(raw_book[i]): lb=float(raw_book[i])
            price[i]=lp; book[i]=lb
        cb=[0.0]*(n+1); cs=[0.0]*(n+1)
        for i in range(n): cb[i+1]=cb[i]+buy[i]; cs[i+1]=cs[i]+sell[i]
        out[ymds(ws)]={'week_sunday':ws,'buy':buy,'sell':sell,'cb':cb,'cs':cs,'price':price,'book':book,
                       'first_trade':min(actual_trades),'last_trade':max(actual_trades),'rows':rows,'trades':trades,
                       'classified':classified,'book_rows':book_rows,'days':expected}
    return out


def gidx(stream,day,sec): return (ymd(day)-stream['week_sunday']).days*DAY_SECONDS+int(sec)

def interval_pressure(stream,lo,hi,pol):
    # inclusive lo..hi
    lo=max(0,int(lo)); hi=min(len(stream['buy'])-1,int(hi))
    if hi<lo: return None
    b=stream['cb'][hi+1]-stream['cb'][lo]; s=stream['cs'][hi+1]-stream['cs'][lo]
    z=b+s
    return None if z<=0 else int(pol)*(b-s)/z

def state(v):
    if v is None or abs(float(v))<1e-12: return 'sparse_or_balanced'
    return 'reload_same' if float(v)>0 else 'switch_opposite'

def val_at(a,i):
    if i<0 or i>=len(a) or not finite(a[i]): return None
    return float(a[i])


def price_outcomes(stream,anchor,pol):
    p0=val_at(stream['price'],anchor); out={}
    for h in HORIZONS:
        stop=anchor+h
        if p0 is None or stop>stream['last_trade']:
            out[str(h)]={'class':None,'signed_displacement_ticks':None,'mfe_ticks':None,'mae_ticks':None,'censored':True}
            continue
        p=val_at(stream['price'],stop)
        vals=[val_at(stream['price'],i) for i in range(anchor,stop+1)]; vals=[x for x in vals if x is not None]
        if p is None or not vals:
            out[str(h)]={'class':None,'signed_displacement_ticks':None,'mfe_ticks':None,'mae_ticks':None,'censored':False}
            continue
        signed=int(pol)*(p-p0)/TICK; oriented=[int(pol)*(x-p0)/TICK for x in vals]
        cls='continuation' if signed>=MATERIAL_TICKS else ('reversal' if signed<=-MATERIAL_TICKS else 'chop')
        out[str(h)]={'class':cls,'signed_displacement_ticks':signed,'mfe_ticks':max(oriented),'mae_ticks':min(oriented),'censored':False}
    return out


def summarize_group(rr):
    out={'n':len(rr),'horizons':{}}
    for h in HORIZONS:
        valid=[r for r in rr if r['checkpoint_outcomes'][str(h)]['class'] is not None and not r['checkpoint_outcomes'][str(h)]['censored']]
        c=Counter(r['checkpoint_outcomes'][str(h)]['class'] for r in valid); n=len(valid)
        disp=[r['checkpoint_outcomes'][str(h)]['signed_displacement_ticks'] for r in valid]
        cont=c['continuation']; rev=c['reversal']; chop=c['chop']
        out['horizons'][str(h)]={'n':n,'continuation_rate':cont/n if n else None,'continuation_wilson95':wilson(cont,n),
                                 'reversal_rate':rev/n if n else None,'reversal_wilson95':wilson(rev,n),
                                 'chop_rate':chop/n if n else None,'net_cont_minus_rev':(cont-rev)/n if n else None,
                                 'disp_median_ticks':med(disp),'disp_q25_ticks':quantile(disp,.25),'disp_q75_ticks':quantile(disp,.75)}
    return out


def by_day(rr):
    return {d:summarize_group([r for r in rr if r['day']==d]) for d in sorted(set(r['day'] for r in rr))}


def reveal_bin_edges(rows,key,qs=(.2,.4,.6,.8)):
    vals=[r[key] for r in rows if finite(r.get(key))]
    return [quantile(vals,q) for q in qs]

def bin_index(v,edges):
    if not finite(v): return None
    for i,e in enumerate(edges):
        if float(v)<=float(e): return i
    return len(edges)

def monotone_table(rows,key,edges):
    out=[]
    for i in range(len(edges)+1):
        z=[r for r in rows if bin_index(r.get(key),edges)==i]
        out.append({'bin':i,'n':len(z),'feature_median':med([r.get(key) for r in z]),'outcomes':summarize_group(z)})
    return out


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--v2-event-table',required=True)
    ap.add_argument('--out-prefix',default='NG_EXHAUSTION_AFTERMATH_TRANSITION_CHECKPOINT_20260817')
    ap.add_argument('raw_days',nargs='+')
    a=ap.parse_args()
    base=load_v2_event_table(a.v2_event_table)
    target_days=sorted(set(x['identity']['day'] for x in base)); streams=load_week_streams(a.raw_days,target_days)
    rows=[]
    for e in base:
        i=e['identity']; ep=e['dynamic_endpoint']; f=e['features_asof_plus60']
        if ep['censored'] or ep['causal_confirmation_offset_s'] is None: raise SystemExit('V2 endpoint unexpectedly censored')
        ws=ymds(sunday_of(ymd(i['day']))); s=streams[ws]
        t0=gidx(s,i['day'],i['t0_second_utc']); end=t0+int(ep['causal_confirmation_offset_s']); cp=end+CHECKPOINT
        pol=int(i['polarity'])
        p_pre=interval_pressure(s,end-19,end,pol); p_prev=interval_pressure(s,end-39,end-20,pol)
        p_post=interval_pressure(s,end+1,cp,pol)
        b_end=val_at(s['book'],end); b_cp=val_at(s['book'],cp)
        row={'split':i['split'],'source_id':i['source_id'],'day':i['day'],'t0_second_utc':i['t0_second_utc'],'polarity':pol,'family':i['family'],
             'alive_through60':bool(f['alive_through60']),'endpoint_confirm_offset_s':int(ep['causal_confirmation_offset_s']),
             'endpoint_pressure20':p_pre,'endpoint_pressure_prev20':p_prev,
             'endpoint_pressure_change20':None if p_pre is None or p_prev is None else p_pre-p_prev,
             'endpoint_book_aligned':None if b_end is None else pol*b_end,
             'post_end_pressure20':p_post,'transition_state':state(p_post),
             'checkpoint_book_aligned':None if b_cp is None else pol*b_cp,
             'checkpoint_book_change_from_endpoint':None if b_end is None or b_cp is None else pol*(b_cp-b_end),
             'checkpoint_censored':cp>s['last_trade']}
        row['checkpoint_outcomes']=price_outcomes(s,cp,pol) if not row['checkpoint_censored'] else {str(h):{'class':None,'signed_displacement_ticks':None,'mfe_ticks':None,'mae_ticks':None,'censored':True} for h in HORIZONS}
        rows.append(row)
    if len(rows)!=3429: raise SystemExit('transition event population drift')

    reveal=[r for r in rows if r['split']=='reveal']; hold=[r for r in rows if r['split']=='holdout']
    pressure_edges=reveal_bin_edges(reveal,'post_end_pressure20')
    summary={'status':'CAUSAL_POST_END_TRANSITION_CHECKPOINT_VALIDATION_COMPLETE','population':{'reveal':len(reveal),'holdout':len(hold),'combined':len(rows)},
             'checkpoint_contract':{'dynamic_endpoint':True,'checkpoint_offset_s':CHECKPOINT,'checkpoint_is_endpoint':False,'price_feature_used':False,
                                    'primary_state':'sign of endpoint+1..endpoint+20 aligned aggressor pressure','holdout_retuning':False},
             'raw_weeks':{k:{x:v[x] for x in ('days','rows','trades','classified','book_rows','first_trade','last_trade')} for k,v in streams.items()},
             'reveal_pressure_quintile_edges':pressure_edges,'splits':{},'family_descriptive':{},
             'no_runway_clock_mutation':True,'permanent_frankie_mutated':False}
    for split,rr in (('reveal',reveal),('holdout',hold)):
        d={'overall':summarize_group(rr),'by_transition_state':{},'collapsed_by60':{},'alive_through60':{},
           'pressure_quintiles_from_reveal':monotone_table(rr,'post_end_pressure20',pressure_edges)}
        for st in ('reload_same','switch_opposite','sparse_or_balanced'):
            z=[r for r in rr if r['transition_state']==st]
            d['by_transition_state'][st]={'pooled':summarize_group(z),'daily':by_day(z)}
        for flag,label in ((False,'collapsed_by60'),(True,'alive_through60')):
            z=[r for r in rr if r['alive_through60']==flag]
            d[label]['overall']=summarize_group(z); d[label]['by_transition_state']={}
            for st in ('reload_same','switch_opposite','sparse_or_balanced'):
                q=[r for r in z if r['transition_state']==st]
                d[label]['by_transition_state'][st]={'pooled':summarize_group(q),'daily':by_day(q)}
        summary['splits'][split]=d
    for fam in ('A','B','C'):
        summary['family_descriptive'][fam]={}
        for split,rr in (('reveal',reveal),('holdout',hold)):
            z=[r for r in rr if r['family']==fam]
            summary['family_descriptive'][fam][split]={'n':len(z),'by_transition_state':{st:summarize_group([r for r in z if r['transition_state']==st]) for st in ('reload_same','switch_opposite','sparse_or_balanced')}}
    Path(a.out_prefix+'.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    with gzip.open(a.out_prefix+'_EVENT_TABLE.jsonl.gz','wt') as f:
        for r in rows: f.write(json.dumps(r,separators=(',',':'))+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=='__main__': main()
