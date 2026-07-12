#!/usr/bin/env python3
"""Macro event-weight study. Explicit release-date lists (FOMC) + derived (NFP
first-Friday). Daily change (FRED yields/SP500) + intraday release-hour (Yahoo
futures ES=F/ZN=F). Yields measured in bps (abs change); equities in %.
Placebo = same instrument, matched non-event days (daily) or same ET hour on
non-event weekdays (intraday).
"""
import csv, json, math, datetime as dt
from collections import defaultdict
from zoneinfo import ZoneInfo
ET = ZoneInfo("America/New_York")
DATA = "/home/user/Markets/data/kalshi_hist"

FOMC = ["2021-01-27","2021-03-17","2021-04-28","2021-06-16","2021-07-28","2021-09-22","2021-11-03","2021-12-15",
"2022-01-26","2022-03-16","2022-05-04","2022-06-15","2022-07-27","2022-09-21","2022-11-02","2022-12-14",
"2023-02-01","2023-03-22","2023-05-03","2023-06-14","2023-07-26","2023-09-20","2023-11-01","2023-12-13",
"2024-01-31","2024-03-20","2024-05-01","2024-06-12","2024-07-31","2024-09-18","2024-11-07","2024-12-18",
"2025-01-29","2025-03-19","2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29","2025-12-10",
"2026-01-28","2026-03-18","2026-04-29","2026-06-17"]
FOMC = set(dt.date.fromisoformat(x) for x in FOMC)

def first_fridays(y0=2016, y1=2026):
    out=set()
    for y in range(y0,y1+1):
        for m in range(1,13):
            d=dt.date(y,m,1)
            while d.weekday()!=4: d+=dt.timedelta(days=1)
            out.add(d)  # first Friday (NFP, 8:30 ET) — ~90% accurate; occasional 2nd-Friday shifts
    return out
NFP = first_fridays()

def load_fred(fid):
    rows=[]
    for d,v in list(csv.reader(open(f"{DATA}/fred_{fid}.csv")))[1:]:
        if v in(".",""):continue
        try: rows.append((dt.date.fromisoformat(d),float(v)))
        except: pass
    rows.sort();return rows

def daily_changes(rows, mode):
    out={}
    for i in range(1,len(rows)):
        d,v=rows[i];dp,vp=rows[i-1]
        if mode=="bps": out[d]=(v-vp)*100.0  # yield pts -> bps
        else:
            if vp>0 and v>0: out[d]=math.log(v/vp)*100.0
    return out

def welch(ev,pl):
    ev=[abs(x) for x in ev];pl=[abs(x) for x in pl]
    ne,npl=len(ev),len(pl)
    if ne<2 or npl<2:return None
    me,mpl=sum(ev)/ne,sum(pl)/npl
    ve=sum((x-me)**2 for x in ev)/(ne-1);vpl=sum((x-mpl)**2 for x in pl)/(npl-1)
    se=math.sqrt(ve/ne+vpl/npl);pooled=math.sqrt(((ne-1)*ve+(npl-1)*vpl)/(ne+npl-2))
    return dict(n_event=ne,n_placebo=npl,mean_abs_event=round(me,4),mean_abs_placebo=round(mpl,4),
                ratio=round(me/mpl,3) if mpl>0 else None, welch_z=round((me-mpl)/se,2) if se>0 else 0,
                cohens_d=round((me-mpl)/pooled,3) if pooled>0 else 0)

def daily_event(fid, dates, mode, label, contract, unit):
    rows=load_fred(fid); ch=daily_changes(rows,mode)
    ev=[ch[d] for d in ch if d in dates]
    pl=[ch[d] for d in ch if d not in dates and d.weekday()<5]
    return dict(event_type=label,kalshi_contract=contract,underlying=fid,unit=unit,
                date_range=[str(rows[0][0]),str(rows[-1][0])],n_events_in_window=len(ev),
                effect_vs_placebo=welch(ev,pl))

def load_60m(fn):
    bars=[]
    for ts,c in list(csv.reader(open(f"{DATA}/{fn}")))[1:]:
        if c in("","."):continue
        t=int(float(ts));bars.append((t,dt.datetime.fromtimestamp(t,ET),float(c)))
    bars.sort();return bars

def hour_ret(bars,mode):
    out=[]
    for i in range(1,len(bars)):
        t,et,c=bars[i];tp,_,cp=bars[i-1]
        if cp<=0 or c<=0 or t-tp>2*3600+300:continue
        r=(c-cp) if mode=="pts" else math.log(c/cp)*100.0
        out.append((et.date(),et.weekday(),et.hour,r))
    return out

def intraday_event(fn, dates, wd, hour, mode, label, contract, sym, unit):
    bars=load_60m(fn); hr=hour_ret(bars,mode)
    ev=[r for dte,w,h,r in hr if h==hour and dte in dates]
    pl=[r for dte,w,h,r in hr if h==hour and w<5 and dte not in dates and (wd is None or w==wd)]
    return dict(event_type=label,kalshi_contract=contract,symbol=sym,unit=unit,
                window=f"ET hour {hour}:00 bar",date_range=[str(bars[0][1].date()),str(bars[-1][1].date())],
                n_events=len(ev),effect_vs_placebo=welch(ev,pl))

if __name__=="__main__":
    out={}
    # FOMC (14:00 ET statement)
    out["FOMC_daily_2yr"]=daily_event("DGS2",FOMC,"bps","FOMC statement -> 2yr yield","KXFEDHIKE","bps")
    out["FOMC_daily_SP500"]=daily_event("SP500",FOMC,"pct","FOMC statement -> S&P500","KXFEDHIKE","%")
    out["FOMC_intraday_ES"]=intraday_event("yh_ES_60m.csv",FOMC,None,14,"pct","FOMC statement -> ES=F (14:00 ET)","KXFEDHIKE","ES=F","%")
    out["FOMC_intraday_ZN"]=intraday_event("yh_ZN_60m.csv",FOMC,None,14,"pct","FOMC statement -> ZN=F 10yr note (14:00 ET)","KXFEDHIKE","ZN=F","%")
    # NFP (first Friday, 8:30 ET)
    out["NFP_daily_2yr"]=daily_event("DGS2",NFP,"bps","Nonfarm Payrolls -> 2yr yield","KXUSNFP","bps")
    out["NFP_daily_SP500"]=daily_event("SP500",NFP,"pct","Nonfarm Payrolls -> S&P500","KXUSNFP","%")
    out["NFP_intraday_ES"]=intraday_event("yh_ES_60m.csv",NFP,4,8,"pct","Nonfarm Payrolls -> ES=F (8:30 ET)","KXUSNFP","ES=F","%")
    out["NFP_intraday_ZN"]=intraday_event("yh_ZN_60m.csv",NFP,4,8,"pct","Nonfarm Payrolls -> ZN=F (8:30 ET)","KXUSNFP","ZN=F","%")
    print(json.dumps(out,indent=2,default=str))
    json.dump(out,open("/home/user/Markets/research/kalshi/hist/macro_results.json","w"),indent=2,default=str)
