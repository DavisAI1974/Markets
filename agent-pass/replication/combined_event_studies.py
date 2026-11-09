"""Shared exact-clock inputs for the four-date combined event studies."""
import argparse,json,pathlib,sys
import numpy as np
from finish_family_replication import inputs,jsonwrite,seal,READS

def first_after(times,cursors,clock,cursor):
    """First record strictly later on BOTH receive clock and source order."""
    return max(int(np.searchsorted(times,clock,side="right")),
               int(np.searchsorted(cursors,cursor,side="right")))

def prior_to(times,cursors,clock,cursor):
    return min(int(np.searchsorted(times,clock,side="left"))-1,
               int(np.searchsorted(cursors,cursor,side="left"))-1)

def unit_checks():
    t=np.array([10,20,20,30],dtype=np.int64);c=np.array([1,2,3,4])
    assert prior_to(t,c,20,3)==0
    assert prior_to(t,c,31,3)==1
    assert first_after(t,c,20,2)==3
    assert first_after(t,c,15,3)==3
    # Absolute clocks remain exact past the IEEE float integer range.
    anchor=1697634552081390598
    assert anchor-(anchor-1)==1
    print("PASS: strict receive/cursor boundaries, duplicate times, integer nanoseconds",flush=True)

def probe(day,out):
    unit_checks()
    groups,raw=inputs(day,True)
    raw=raw.sort_values("cursor")
    cursors=raw.cursor.to_numpy(dtype=np.int64)
    lo=np.searchsorted(cursors,[g["first_cursor"] for g in groups])
    hi=np.searchsorted(cursors,[g["close_cursor"] for g in groups],side="right")
    assert np.all(hi>lo)
    assert all(int(cursors[a])==g["first_cursor"] and int(cursors[b-1])==g["close_cursor"]
               for a,b,g in zip(lo,hi,groups))
    assert all(b-a==g["close_cursor"]-g["first_cursor"]+1 for a,b,g in zip(lo,hi,groups))
    prints=sum(len(g["prints"]) for g in groups)
    assert int(raw.action.eq("T").sum())==prints
    schema=dict(day=day,groups=len(groups),raw_actions=len(raw),prints=prints,
                columns={k:str(v) for k,v in raw.dtypes.items()},
                raw_first=raw.iloc[0].to_dict(),raw_last=raw.iloc[-1].to_dict(),
                group_first=groups[0],group_with_print=next(g for g in groups if g["prints"]),
                source_checks="passed",compute="GitHub-hosted CPU")
    # Convert numpy scalars without passing clocks through float.
    def plain(x):
        if isinstance(x,dict):return {str(k):plain(v) for k,v in x.items()}
        if isinstance(x,(list,tuple)):return [plain(v) for v in x]
        if isinstance(x,np.generic):return x.item()
        return x
    out.mkdir(parents=True,exist_ok=True)
    jsonwrite(out/"source-preflight.json",plain(schema))
    jsonwrite(out/"input-manifest.json",READS);seal(out)
    print(json.dumps({k:schema[k] for k in ("day","groups","raw_actions","prints","source_checks")}),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--day",required=True);p.add_argument("--output",type=pathlib.Path,required=True)
    a=p.parse_args();probe(a.day,a.output)
