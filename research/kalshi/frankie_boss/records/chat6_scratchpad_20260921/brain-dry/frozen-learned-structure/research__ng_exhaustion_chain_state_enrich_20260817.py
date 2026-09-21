#!/usr/bin/env python3
from __future__ import annotations
import argparse,gzip,json
from pathlib import Path
from datetime import timedelta

from ng_exhaustion_week_continuous_roster_20260817 import load_week,parse_day,d8,s8,sunday_of,finite,_fill_curve,PRE


def read_events(path):
    out=[]
    with gzip.open(path,'rt') as f:
        for line in f:
            if line.strip():out.append(json.loads(line))
    if not out:raise SystemExit('empty roster')
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--roster-events',required=True); ap.add_argument('--out-prefix',default='NG_EXHAUSTION_CHAIN_STATE_20260817'); ap.add_argument('raw_days',nargs='+'); a=ap.parse_args()
    events=read_events(a.roster_events); pby={parse_day(p):p for p in a.raw_days}; byweek={}
    for e in events:byweek.setdefault(e['week_sunday'],[]).append(e)
    enriched=[]; summaries={}
    for w,evs in sorted(byweek.items()):
        ws=d8(w); stream=load_week(list(pby.values()),ws); evs=sorted(evs,key=lambda x:x['t_week_second'])
        for e in evs:
            t=int(e['t_week_second']); pol=int(e['polarity'])
            vals=[pol*stream['flow'][t+dt] if finite(stream['flow'][t+dt]) else None for dt in range(-PRE,1)]
            pre=_fill_curve(vals)
            if len(pre)!=61:raise SystemExit('pre curve length drift')
            e2=dict(e)
            e2['chain_membership_state']={'pre_roll20_oriented_t_minus60_to_t0':[float(x) for x in pre],'polarity':pol,
                                          'price_used':False,'post_t0_used':False,'family_used':False,'time_used':False,
                                          'endpoint_used':False,'book_used':False,'event_gap_used':False}
            enriched.append(e2)
        summaries[w]={'events':len(evs),'first_event_week_second':int(evs[0]['t_week_second']),'last_event_week_second':int(evs[-1]['t_week_second'])}
    Path(a.out_prefix+'.json').write_text(json.dumps({'status':'CHAIN_MEMBERSHIP_PRESTATE_TABLE_COMPLETE','weeks':summaries,'events':len(enriched),
      'membership_features':['61-sample oriented pre-roll20 curve','raw polarity'],'forbidden_features_confirmed':True},indent=2,sort_keys=True)+'\n')
    with gzip.open(a.out_prefix+'_EVENTS.jsonl.gz','wt') as f:
        for e in enriched:f.write(json.dumps(e,separators=(',',':'))+'\n')
    print(json.dumps({'events':len(enriched),'weeks':summaries},indent=2))
if __name__=='__main__':main()
