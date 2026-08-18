#!/usr/bin/env python3
from __future__ import annotations
import argparse,bisect,gzip,json,re
from collections import defaultdict
from datetime import datetime,timedelta
from pathlib import Path

import ng_exhaustion_exact_d1_agents_20260818 as core
from ng_dipole_runway_audit import TICK

def day_from_name(p):
    m=re.search(r'(20\d{6})',Path(p).name)
    if not m:raise SystemExit(f'cannot parse day {p}')
    return m.group(1)
def sunday(s):return datetime.strptime(s,'%Y%m%d')
def load_week_prices(raw_paths,week):
    sun=sunday(week);pts=[]
    for p in raw_paths:
        d=day_from_name(p);di=(datetime.strptime(d,'%Y%m%d')-sun).days
        if di<0 or di>5:continue
        with gzip.open(p,'rt') as f:
            for line in f:
                r=json.loads(line)
                if r.get('action')!='T':continue
                px=float(r.get('price',0) or 0)
                if px<=0:continue
                ts=float(r.get('ts_event',r.get('ts',0.0)));sec=int(ts)%86400;pts.append((di*86400+sec,px))
    pts.sort();return pts
def path_stats(pts,start,end,pol):
    if not pts or end<=start:return None
    idx=[x[0] for x in pts];j=max(0,bisect.bisect_right(idx,start)-1);k=bisect.bisect_right(idx,end)
    seg=pts[j:k]
    if len(seg)<2:return None
    p0=seg[0][1];p1=seg[-1][1];oriented=[pol*(p-p0)/TICK for _,p in seg];changes=[seg[i][1]-seg[i-1][1] for i in range(1,len(seg))]
    total=sum(abs(x) for x in changes);signed=pol*(p1-p0)/TICK
    return {'trade_points':len(seg),'duration_seconds':end-start,'signed_endpoint_ticks':signed,'mfe_ticks':max(oriented),'mae_ticks':min(oriented),'path_efficiency':abs(p1-p0)/total if total>0 else None,'aligned_change_fraction':sum(pol*x>0 for x in changes)/len(changes) if changes else None,'entry_price':p0,'exit_price':p1}
def summarize(rows,key):return core.summary([r[key] for r in rows if core.finite(r.get(key))])
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base',required=True);ap.add_argument('--held',required=True);ap.add_argument('--base-lineage',required=True);ap.add_argument('--held-lineage',required=True);ap.add_argument('--summary',required=True);ap.add_argument('--raw-dir',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
    weeks=json.load(open(a.summary))['weeks'];events=core.load_events(a.base,a.held);lineage=core.load_lineage(a.base_lineage,a.held_lineage);d1,model=core.d1_records(events,lineage,weeks);longfam=model['labels'][-1]
    longweeks=sorted(set(r['week'] for r in d1 if r['block']!='held' and r['duration_family']==longfam));raw=list(Path(a.raw_dir).glob('NG_*.jsonl.gz'));out=[]
    for w in longweeks:
        wp=[p for p in raw if day_from_name(p)>=w and day_from_name(p)<=(sunday(w)+timedelta(days=5)).strftime('%Y%m%d')];pts=load_week_prices(wp,w)
        for r in [z for z in d1 if z['week']==w]:
            o=events[w][r['origin_seq']];d=events[w][r['origin_seq']+1]
            if o.get('confirm') is None:continue
            start=int(o['confirm'])+60;end=int(d['t0']);z=path_stats(pts,start,end,o['pol'])
            if z is None:continue
            z.update({'week':w,'block':r['block'],'pair':r['pair'],'duration_family':r['duration_family'],'elapsed_origin_to_desc':r['elapsed'],'origin_event_id':r['origin_event_id'],'desc_event_id':r['desc_event_id'],'origin_wall_to_desc_t0':r['origin_wall_to_desc_t0']});out.append(z)
    cells={}
    for fam in model['labels']:
        R=[r for r in out if r['duration_family']==fam];cells[fam]={'n':len(R),'signed_endpoint_ticks':summarize(R,'signed_endpoint_ticks'),'mfe_ticks':summarize(R,'mfe_ticks'),'mae_ticks':summarize(R,'mae_ticks'),'path_efficiency':summarize(R,'path_efficiency'),'aligned_change_fraction':summarize(R,'aligned_change_fraction'),'duration_seconds':summarize(R,'duration_seconds')}
    res={'status':'EXACT_D1_RAWPATH_AGENT_COMPLETE','long_family':longfam,'long_case_weeks':longweeks,'train_family_centers_seconds':model['centers'],'family_summaries':cells,'records':out,'guard':'raw path uses frozen event indices only; no redetection and no claim that realized long-family identity was known at origin','promotion_performed':False,'protected_mutations':{'detector':False,'canonical_rows':False,'runway_clock':False,'permanent_frankie':False,'frankie_1':False,'spawn_py':False,'ssos_play':False}}
    Path(a.out).write_text(json.dumps(res,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
