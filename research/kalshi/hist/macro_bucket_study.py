#!/usr/bin/env python3
"""PHASE-2 / WEAK-PROXY macro bucketing (NFP). LABELLED WEAK: the real consensus is
only obtainable FORWARD via ForexFactory. Here the surprise proxy = NFP monthly
change (FRED PAYEMS diff) minus its trailing-12-month average (a TREND expectation,
NOT the street number). Reaction = signed ES=F / ZN=F release-hour (8:30 ET) move.
Convention: hot payrolls (actual > trend) => hawkish => bonds DOWN (yields up),
stocks ambiguous. We report bond-direction hit-rate (hot -> ZN down)."""
import csv, json, math, datetime as dt
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
DATA = "/home/user/Markets/data/kalshi_hist"

def first_friday(y,m):
    d=dt.date(y,m,1)
    while d.weekday()!=4: d+=dt.timedelta(days=1)
    return d

def payems_surprise():
    rows=[]
    for d,v in list(csv.reader(open(f"{DATA}/fred_PAYEMS.csv")))[1:]:
        if v in(".",""):continue
        rows.append((dt.date.fromisoformat(d),float(v)))
    rows.sort()
    ch=[(rows[i][0],rows[i][1]-rows[i-1][1]) for i in range(1,len(rows))]  # monthly change (~NFP)
    out=[]
    for i in range(12,len(ch)):
        trend=sum(c for _,c in ch[i-12:i])/12.0
        d,c=ch[i]
        # PAYEMS is stamped 1st-of-month for the reference month; NFP for ref month M
        # is released the first Friday of M+1.
        rel_m=d.month%12+1; rel_y=d.year+(1 if d.month==12 else 0)
        out.append((first_friday(rel_y,rel_m), c-trend))  # (release_date, surprise vs trend)
    return out

def rel_hour_map(fn,hour=8):
    bars=[]
    for ts,c in list(csv.reader(open(f"{DATA}/{fn}")))[1:]:
        if c in("","."):continue
        t=int(float(ts));bars.append((t,dt.datetime.fromtimestamp(t,ET),float(c)))
    bars.sort();m={}
    for i in range(1,len(bars)):
        t,et,c=bars[i];tp,_,cp=bars[i-1]
        if cp<=0 or c<=0 or t-tp>2*3600+300:continue
        if et.hour==hour: m[et.date()]=math.log(c/cp)*100.0
    return m

def study(sym,fn,hot_sign):
    """hot_sign=-1 for ZN (hot payrolls -> bonds down); +1 sign means reaction should
    match sign(surprise)*hot_sign for the fundamental to 'work'."""
    surp=payems_surprise(); rm=rel_hour_map(fn)
    recs=[]
    for rel,s in surp:
        r=None
        for off in (0,1,-1):
            if rel+dt.timedelta(days=off) in rm: r=rm[rel+dt.timedelta(days=off)];break
        if r is None: continue
        recs.append((s,r))
    asurp=sorted(abs(s) for s,_ in recs); t1=asurp[len(asurp)//3] if asurp else 0
    meaningful=[(s,r) for s,r in recs if abs(s)>t1]
    # fundamental works if reaction sign == hot_sign*sign(surprise)
    nm=len(meaningful)
    hit=sum(1 for s,r in meaningful if (r>0)==((hot_sign*s)>0))/nm if nm else None
    hz=(hit-0.5)/math.sqrt(0.25/nm) if nm else None
    buckets={}
    for s,r in recs:
        if abs(s)<=t1: b="in-line (stand-aside)"
        else:
            hot="hot" if s>0 else "cool"
            works=(r>0)==((hot_sign*s)>0)
            b=f"{hot}-payrolls -> {'fundamental' if works else 'counter'}"
        buckets.setdefault(b,[]).append(r)
    bs={k:dict(N=len(v),mean_signed=round(sum(v)/len(v),4),pct_up=round(sum(1 for x in v if x>0)/len(v),3)) for k,v in buckets.items()}
    return dict(symbol=sym,n_matched=len(recs),n_meaningful=nm,
                directional_hitrate=round(hit,3) if hit else None,
                hitrate_z_vs_placebo=round(hz,2) if hz is not None else None,
                buckets=bs)

if __name__=="__main__":
    out=dict(
      _PROXY_WARNING="WEAK/PHASE-2: surprise = NFP vs trailing-12mo TREND, NOT street consensus. Real version needs ForexFactory forward polling. Intraday reaction window only ~730d (small N). Interpret as directional, not sized.",
      NFP_ZN_bonds=study("ZN=F","yh_ZN_60m.csv",-1),  # hot payrolls -> bonds down
      NFP_ES_stocks=study("ES=F","yh_ES_60m.csv",-1), # hot payrolls -> stocks down (risk/rates), ambiguous
    )
    json.dump(out,open("/home/user/Markets/research/kalshi/hist/macro_bucket_results.json","w"),indent=2,default=str)
    for k,v in out.items():
        if k.startswith("_"): continue
        print(f"{k}: n={v['n_matched']} nm={v['n_meaningful']} hitrate={v['directional_hitrate']} z={v['hitrate_z_vs_placebo']}")
        for b,s in v["buckets"].items(): print(f"   {b:<38} N={s['N']:<3} mean_signed={s['mean_signed']:+.3f}% %up={s['pct_up']}")
