#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo

from ng_exhaustion_live_clock import FrozenPreFamilyClassifier, _fill_curve

DAY_SECONDS=86400
ROLL=20
PRE=60
PEAK_Q=.85
LOCAL_RADIUS=5
REFRACTORY=45
PERSIST=3
MARKET_TZ=ZoneInfo('America/New_York')


def finite(x):
    try:return math.isfinite(float(x))
    except Exception:return False

def quantile(xs,q):
    a=sorted(float(x) for x in xs if finite(x))
    if not a:return float('nan')
    if len(a)==1:return a[0]
    z=q*(len(a)-1); i=int(math.floor(z)); j=min(i+1,len(a)-1); w=z-i
    return a[i]*(1-w)+a[j]*w

def finite_median(xs):
    a=sorted(float(x) for x in xs if finite(x)); return median(a) if a else float('nan')
def parse_day(path):
    m=re.search(r'(20\d{6})',Path(path).name)
    if not m:raise SystemExit(f'cannot parse date from {path}')
    return m.group(1)
def d8(s):return date(int(s[:4]),int(s[4:6]),int(s[6:8]))
def s8(d):return d.strftime('%Y%m%d')
def sunday_of(d):return d-timedelta(days=(d.weekday()+1)%7)
def epoch_midnight_utc(d):return int(datetime(d.year,d.month,d.day,tzinfo=timezone.utc).timestamp())


def load_frozen_target(path):
    out={}
    with gzip.open(path,'rt') as f:
        for line in f:
            e=json.loads(line); i=e['identity']
            k=(str(i['day']),int(i['t0_second_utc']),int(i['polarity']))
            out[k]={'split':i['split'],'family':i['family'],'source_id':i['source_id']}
    if len(out)!=3429:raise SystemExit(f'frozen target identity drift {len(out)}')
    return out


def load_week(paths,ws):
    byday={parse_day(p):p for p in paths}
    days=[s8(ws+timedelta(days=i)) for i in range(6)]
    missing=[d for d in days if d not in byday]
    if missing:raise SystemExit(f'missing week files {s8(ws)}: {missing}')
    n=6*DAY_SECONDS; buy=[0.0]*n; sell=[0.0]*n; trade_idx=[]
    rows=trades=classified=midpoint_skip=nobook_skip=0
    for di,d in enumerate(days):
        with gzip.open(byday[d],'rt') as f:
            for line in f:
                r=json.loads(line); rows+=1
                if r.get('action')!='T':continue
                trades+=1
                ts=float(r.get('ts_event',r.get('ts',0.0))); sec=int(ts)%DAY_SECONDS; idx=di*DAY_SECONDS+sec
                px=float(r.get('price',0.0) or 0.0); sz=float(r.get('size',r.get('qty',0.0)) or 0.0)
                if px>0:trade_idx.append(idx)
                bid0=float(r.get('bid_px_00',0.0) or 0.0); ask0=float(r.get('ask_px_00',0.0) or 0.0)
                if not (px>0 and sz>0 and bid0>0 and ask0>0 and ask0>=bid0):
                    nobook_skip+=1; continue
                mid=.5*(bid0+ask0)
                if px>mid:buy[idx]+=sz; classified+=1
                elif px<mid:sell[idx]+=sz; classified+=1
                else:midpoint_skip+=1
    if not trade_idx:raise SystemExit(f'no trades week {s8(ws)}')
    cb=[0.0]*(n+1); cs=[0.0]*(n+1)
    for i in range(n):cb[i+1]=cb[i]+buy[i]; cs[i+1]=cs[i]+sell[i]
    flow=[float('nan')]*n
    for i in range(n):
        lo=max(0,i-ROLL+1); b=cb[i+1]-cb[lo]; s=cs[i+1]-cs[lo]; z=b+s
        if z>0:flow[i]=(b-s)/z
    return {'week_sunday':ws,'days':days,'flow':flow,'first_trade':min(trade_idx),'last_trade':max(trade_idx),
            'rows':rows,'trades':trades,'classified':classified,'midpoint_skip':midpoint_skip,'nobook_skip':nobook_skip}


def detect_week(stream):
    flow=stream['flow']; first=stream['first_trade']; last=stream['last_trade']; days=stream['days']
    thresholds={}
    for di,d in enumerate(days):
        lo=di*DAY_SECONDS; hi=(di+1)*DAY_SECONDS
        thresholds[d]=quantile([abs(v) for v in flow[lo:hi] if finite(v)],PEAK_Q)
    cand=[]
    lo=max(first+PRE,PRE); hi=min(last-LOCAL_RADIUS,len(flow)-LOCAL_RADIUS-1)
    for t in range(lo,hi+1):
        v=flow[t]
        if not finite(v):continue
        di=t//DAY_SECONDS; day=days[di]
        thr=thresholds[day]
        if not finite(thr) or abs(v)<thr:continue
        local=[abs(flow[j]) for j in range(t-LOCAL_RADIUS,t+LOCAL_RADIUS+1) if finite(flow[j])]
        if not local or abs(v)<max(local)-1e-12:continue
        base=finite_median(abs(flow[j]) for j in range(max(0,t-30),max(0,t-9)) if finite(flow[j]))
        if not finite(base):base=0.0
        prom=abs(v)-base
        cand.append((t,abs(v),prom))
    cand.sort(key=lambda z:(z[2],z[1]),reverse=True)
    picked=[]
    for row in cand:
        t=row[0]
        if any(abs(t-p[0])<REFRACTORY for p in picked):continue
        picked.append(row)
    picked.sort(key=lambda z:z[0])
    return picked,thresholds


def endpoint(flow,t0,pol,last_trade):
    last=float(flow[t0]); run=0
    for sec in range(t0+1,last_trade+1):
        v=flow[sec]
        if finite(v):last=float(v)
        run=run+1 if pol*last<=0 else 0
        if run>=PERSIST:return {'onset':sec-(PERSIST-1),'confirm':sec}
    return None


def event_clock(stream,t):
    ws=stream['week_sunday']; di=t//DAY_SECONDS; sec=t%DAY_SECONDS; day=ws+timedelta(days=di)
    epoch=epoch_midnight_utc(day)+sec
    u=datetime.fromtimestamp(epoch,timezone.utc); local=u.astimezone(MARKET_TZ)
    return {'day':s8(day),'second_utc':sec,'epoch_utc':epoch,'timestamp_utc':u.isoformat(),
            'timestamp_market_tz':local.isoformat(),'market_clock':local.strftime('%H:%M:%S'),
            'market_date':local.strftime('%Y-%m-%d'),'he_label':local.hour+1,
            'seconds_since_week_first_trade':t-stream['first_trade']}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--frozen-target-table',required=True)
    ap.add_argument('--family-classifier',required=True)
    ap.add_argument('--out-prefix',default='NG_EXHAUSTION_WEEK_CONTINUOUS_ROSTER_20260817')
    ap.add_argument('raw_days',nargs='+')
    a=ap.parse_args()
    target=load_frozen_target(a.frozen_target_table)
    classifier=FrozenPreFamilyClassifier.load(a.family_classifier)
    pby={parse_day(p):p for p in a.raw_days}
    weeks=sorted(set(sunday_of(d8(k[0])) for k in target))
    all_events=[]; summaries={}; target_seen={}; extras=[]
    for ws in weeks:
        stream=load_week(list(pby.values()),ws); peaks,thresholds=detect_week(stream); events=[]
        for t,mag,prom in peaks:
            raw0=stream['flow'][t]
            if not finite(raw0) or abs(raw0)<1e-9:continue
            pol=1 if raw0>0 else -1
            pre=_fill_curve([pol*stream['flow'][t+dt] if finite(stream['flow'][t+dt]) else None for dt in range(-PRE,1)])
            fam=classifier.classify(pre)
            ep=endpoint(stream['flow'],t,pol,stream['last_trade'])
            clk=event_clock(stream,t); k=(clk['day'],clk['second_utc'],pol); frozen=target.get(k)
            rec={'week_sunday':s8(ws),'week_index':len(events),'t_week_second':t,'clock':clk,'polarity':pol,
                 'peak_abs':mag,'pre_prominence':prom,'day_native_peak_threshold':thresholds[clk['day']],
                 'family_posthoc':fam.family,'family_distances_posthoc':list(fam.distances),
                 'endpoint':{'censored':ep is None,'structural_onset_week_second':None if ep is None else ep['onset'],
                             'causal_confirmation_week_second':None if ep is None else ep['confirm'],
                             'structural_onset_offset_s':None if ep is None else ep['onset']-t,
                             'causal_confirmation_offset_s':None if ep is None else ep['confirm']-t},
                 'frozen_target_match':frozen is not None,
                 'frozen_target_split':None if frozen is None else frozen['split'],
                 'frozen_target_family':None if frozen is None else frozen['family']}
            if frozen:
                target_seen[k]=rec
                if fam.family!=frozen['family']:raise SystemExit(f'family reproduction mismatch {k}: {fam.family} vs {frozen["family"]}')
            elif clk['day'] in {x[0] for x in target}:extras.append({'day':clk['day'],'t0':clk['second_utc'],'polarity':pol,'week':s8(ws)})
            events.append(rec)
        for i,r in enumerate(events):
            if i+1<len(events):
                n=events[i+1]; dt=n['t_week_second']-r['t_week_second']; conf=r['endpoint']['causal_confirmation_week_second']
                r['next_event']={'week_index':n['week_index'],'dt_s':dt,'polarity':n['polarity'],'same_polarity':n['polarity']==r['polarity'],
                                 'starts_before_current_confirmation':None if conf is None else n['t_week_second']<=conf}
            else:r['next_event']=None
        all_events.extend(events)
        summaries[s8(ws)]={'days':stream['days'],'raw_rows':stream['rows'],'trades':stream['trades'],'classified_trades':stream['classified'],
                           'first_trade_week_second':stream['first_trade'],'last_trade_week_second':stream['last_trade'],
                           'event_count':len(events),'endpoint_censored_n':sum(e['endpoint']['censored'] for e in events),
                           'family_counts_posthoc':dict(Counter(e['family_posthoc'] for e in events)),
                           'day_native_peak_thresholds':thresholds}
    missing=sorted(set(target)-set(target_seen))
    if missing:raise SystemExit(f'continuous roster failed to reproduce {len(missing)} frozen target events; first={missing[:10]}')
    summary={'status':'WEEK_CONTINUOUS_EXHAUSTION_ROSTER_COMPLETE_NO_CHAIN_LABELS','weeks':summaries,
             'event_count':len(all_events),'frozen_target_reproduced_n':len(target_seen),'frozen_target_expected_n':len(target),
             'frozen_family_reproduction_mismatches':0,'extra_detected_events_on_frozen_target_days':extras,
             'detector_contract':{'roll_s':ROLL,'day_native_peak_quantile':PEAK_Q,'local_radius_s':LOCAL_RADIUS,'refractory_s':REFRACTORY,
                                  'pre_prominence_window':'t0-30..t0-10','cross_midnight_flow':True,'cross_midnight_local_max':True,
                                  'cross_midnight_prominence':True,'cross_midnight_refractory':True,'price_used_for_event_detection':False,
                                  'daily_file_boundary_is_reset':False},
             'chain_labels_assigned':False,'chain_categories_assigned':False,'time_used_for_membership':False,
             'no_runway_clock_mutation':True,'permanent_frankie_mutated':False}
    Path(a.out_prefix+'.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    with gzip.open(a.out_prefix+'_EVENTS.jsonl.gz','wt') as f:
        for e in all_events:f.write(json.dumps(e,separators=(',',':'))+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))

if __name__=='__main__':main()
