#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,json
from collections import Counter
from pathlib import Path

from ng_exhaustion_live_clock import FrozenPreFamilyClassifier,_fill_curve
from ng_exhaustion_week_continuous_roster_20260817 import (
    load_frozen_target,parse_day,d8,s8,sunday_of,load_week,detect_week,endpoint,event_clock,finite,PRE
)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--frozen-target-table',required=True); ap.add_argument('--family-classifier',required=True)
    ap.add_argument('--out-prefix',default='NG_EXHAUSTION_WEEK_CHAIN_STATE_ROSTER_20260817'); ap.add_argument('raw_days',nargs='+'); a=ap.parse_args()
    target=load_frozen_target(a.frozen_target_table); classifier=FrozenPreFamilyClassifier.load(a.family_classifier)
    pby={parse_day(p):p for p in a.raw_days}; weeks=sorted(set(sunday_of(d8(k[0])) for k in target)); target_days=set(k[0] for k in target)
    all_events=[]; summaries={}; target_seen={}; extras=[]
    for ws in weeks:
        stream=load_week(list(pby.values()),ws); peaks,thresholds=detect_week(stream); events=[]
        for t,mag,prom in peaks:
            raw0=stream['flow'][t]
            if not finite(raw0) or abs(raw0)<1e-9:continue
            pol=1 if raw0>0 else -1
            pre=_fill_curve([pol*stream['flow'][t+dt] if finite(stream['flow'][t+dt]) else None for dt in range(-PRE,1)])
            fam=classifier.classify(pre); ep=endpoint(stream['flow'],t,pol,stream['last_trade']); clk=event_clock(stream,t)
            k=(clk['day'],clk['second_utc'],pol); frozen=target.get(k)
            rec={'week_sunday':s8(ws),'week_index':len(events),'t_week_second':t,'clock':clk,'polarity':pol,
                 'chain_membership_state':{'pre_roll20_oriented_t_minus60_to_t0':[float(x) for x in pre],'polarity':pol,
                    'price_used':False,'post_t0_used':False,'family_used':False,'time_used':False,'endpoint_used':False,'book_used':False,'event_gap_used':False},
                 'endpoint_posthoc':{'censored':ep is None,'structural_onset_offset_s':None if ep is None else ep['onset']-t,
                    'causal_confirmation_offset_s':None if ep is None else ep['confirm']-t},
                 'descriptors_posthoc':{'peak_abs':mag,'pre_prominence':prom,'day_native_peak_threshold':thresholds[clk['day']],
                    'family':fam.family,'family_distances':list(fam.distances)},
                 'frozen_target_match':frozen is not None,'frozen_target_split':None if frozen is None else frozen['split'],
                 'frozen_target_family':None if frozen is None else frozen['family']}
            if frozen:
                target_seen[k]=rec
                if fam.family!=frozen['family']:raise SystemExit(f'family mismatch {k}')
            elif clk['day'] in target_days:extras.append({'day':clk['day'],'t0':clk['second_utc'],'polarity':pol,'week':s8(ws)})
            events.append(rec)
        for i,e in enumerate(events):
            e['next_event_target']=None if i+1==len(events) else {'next_index':i+1,'same_polarity':events[i+1]['polarity']==e['polarity'],'dt_s_posthoc':events[i+1]['t_week_second']-e['t_week_second']}
        all_events.extend(events)
        summaries[s8(ws)]={'event_count':len(events),'endpoint_censored_n':sum(e['endpoint_posthoc']['censored'] for e in events),
                           'family_counts_posthoc':dict(Counter(e['descriptors_posthoc']['family'] for e in events)),
                           'first_trade_week_second':stream['first_trade'],'last_trade_week_second':stream['last_trade']}
    missing=sorted(set(target)-set(target_seen))
    if missing:raise SystemExit(f'missing frozen target events {len(missing)} first={missing[:10]}')
    summary={'status':'WEEK_CONTINUOUS_CHAIN_PRESTATE_ROSTER_COMPLETE_NO_CHAIN_LABELS','weeks':summaries,'event_count':len(all_events),
             'frozen_target_reproduced_n':len(target_seen),'frozen_target_expected_n':len(target),'family_mismatches':0,
             'extra_detected_events_on_frozen_target_days':extras,'membership_features':['61-sample oriented pre-roll20 curve','raw polarity'],
             'price_used_for_membership':False,'post_t0_used_for_membership':False,'family_used_for_membership':False,
             'time_used_for_membership':False,'endpoint_used_for_membership':False,'event_gap_used_for_membership':False,
             'chain_labels_assigned':False,'chain_categories_assigned':False}
    Path(a.out_prefix+'.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    with gzip.open(a.out_prefix+'_EVENTS.jsonl.gz','wt') as f:
        for e in all_events:f.write(json.dumps(e,separators=(',',':'))+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__':main()
