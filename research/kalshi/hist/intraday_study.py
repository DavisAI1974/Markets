#!/usr/bin/env python3
"""Intraday release-window event study using Yahoo 60m futures bars (~730d).
Isolates the 10:30 ET release by measuring the return of the release-hour bar on
release days vs the SAME hour on non-release weekdays (clean placebo).
"""
import csv, json, math, datetime as dt
from collections import defaultdict
try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:
    ET = None

DATA = "/home/user/Markets/data/kalshi_hist"

def load_60m(fn):
    bars = []
    with open(f"{DATA}/{fn}") as f:
        r = csv.reader(f); next(r)
        for ts, c in r:
            if c in ("", "."): continue
            t = int(float(ts)); cl = float(c)
            et = dt.datetime.fromtimestamp(t, ET) if ET else dt.datetime.utcfromtimestamp(t)
            bars.append((t, et, cl))
    bars.sort()
    return bars

def hour_returns(bars):
    """(et_datetime, weekday, hour_ET, ret_of_this_bar_vs_prev_bar)."""
    out = []
    for i in range(1, len(bars)):
        t, et, c = bars[i]; tp, etp, cp = bars[i-1]
        if cp <= 0 or c <= 0: continue
        # only consecutive same-session hourly steps (<=2h gap) to avoid overnight
        if t - tp > 2*3600 + 300:
            out.append((et, et.weekday(), et.hour, None)); continue
        out.append((et, et.weekday(), et.hour, math.log(c/cp)))
    return out

def stats(xs):
    xs = [x for x in xs if x is not None]
    n = len(xs)
    if n == 0: return dict(n=0)
    m = sum(xs)/n
    ma = sum(abs(x) for x in xs)/n
    sd = math.sqrt(sum((x-m)**2 for x in xs)/(n-1)) if n > 1 else 0.0
    return dict(n=n, mean=m, mean_abs=ma, sd=sd)

def welch(ev, pl):
    ev=[abs(x) for x in ev if x is not None]; pl=[abs(x) for x in pl if x is not None]
    ne,npl=len(ev),len(pl)
    if ne<2 or npl<2: return None
    me,mpl=sum(ev)/ne,sum(pl)/npl
    ve=sum((x-me)**2 for x in ev)/(ne-1); vpl=sum((x-mpl)**2 for x in pl)/(npl-1)
    se=math.sqrt(ve/ne+vpl/npl); pooled=math.sqrt(((ne-1)*ve+(npl-1)*vpl)/(ne+npl-2))
    return dict(n_event=ne,n_placebo=npl,mean_abs_event=me,mean_abs_placebo=mpl,
                ratio=me/mpl if mpl>0 else None, welch_z=(me-mpl)/se if se>0 else 0.0,
                cohens_d=(me-mpl)/pooled if pooled>0 else 0.0)

def release_hour_study(fn, release_wd, release_hour_et, label, contract, sym):
    bars = load_60m(fn)
    hr = hour_returns(bars)
    # release-hour bar: the bar whose ET hour == release_hour_et (contains 10:30 if hour=10)
    ev = [r for (et,wd,h,r) in hr if wd==release_wd and h==release_hour_et and r is not None]
    # placebo: same ET hour, other weekdays (Mon-Fri excl release day)
    pl = [r for (et,wd,h,r) in hr if wd!=release_wd and wd<5 and h==release_hour_et and r is not None]
    eff = welch(ev, pl)
    # also directional: mean signed move (should be ~0 unconditional, surprise-driven)
    return dict(event_type=label, kalshi_contract=contract, symbol=sym,
                window=f"release-hour bar (ET hour {release_hour_et}:00-{release_hour_et+1}:00, contains ~10:30 release) on {['Mon','Tue','Wed','Thu','Fri'][release_wd]}",
                date_range=[str(bars[0][1].date()), str(bars[-1][1].date())],
                event_hour=stats(ev), placebo_same_hour_other_days=stats(pl),
                effect_vs_placebo=eff)

if __name__ == "__main__":
    out = {}
    # EIA Petroleum: Wed 10:30 ET -> CL=F (bar hour 10)
    out["EIA_petroleum_WTI_intraday"] = release_hour_study("yh_CL_60m.csv", 2, 10,
        "EIA Weekly Petroleum Status (crude) — intraday", "KXWTI", "CL=F")
    # EIA NatGas Storage: Thu 10:30 ET -> NG=F
    out["EIA_natgas_storage_intraday"] = release_hour_study("yh_NG_60m.csv", 3, 10,
        "EIA Weekly Natural Gas Storage — intraday", "KXNATGASD", "NG=F")
    print(json.dumps(out, indent=2, default=str))
    with open(f"/home/user/Markets/research/kalshi/hist/intraday_results.json","w") as f:
        json.dump(out, f, indent=2, default=str)
