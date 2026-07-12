#!/usr/bin/env python3
"""(1) REGIME-SPLIT natgas bucketing — DATA-DISCOVERED regimes, NOT calendar months.
Founder correction: modern gas demand is DOUBLE-HUMPED in temperature (cold->heating draws,
hot->power-burn draws), low in mild spring/fall shoulders. We classify each release by its
ACTUAL weekly degree-days (discovered thresholds from the observed humps), so warm/cold years
reassign weeks automatically:
  WINTER-WITHDRAWAL   : weekly gas-wtd HDD > 120           (HDD hump; deep draws)
  SUMMER-WITHDRAWAL   : weekly pop-wtd CDD > 40            (CDD power-burn hump; build-minimum)
  SPRING-INJECTION    : low DD, ISO week < 27              (mild shoulder, builds)
  FALL-INJECTION      : low DD, ISO week >= 27             (mild shoulder, builds)
Discovery evidence (national median weekly change): draws wk46-13 (HDD 124-217), build-MINIMUM
wk28-31 (+26..+35 Bcf) coincident with CDD peak (80-88) = the summer demand hump; builds wk14-45.
Honest: on the NATIONAL AGGREGATE summer is a build-MINIMUM, not a net draw; peak-heat weeks
approach zero build. Regime by degree-days captures the demand hump regardless of the sign.
Bucket per REGIME x surprise-sign x reaction-sign."""
import json, datetime as dt, math
from collections import defaultdict
import sys; sys.path.insert(0,"/home/user/Markets/research/kalshi/hist")
from eia_bucket_study import (load_eia, weekly_changes, seasonal_surprise,
    next_weekday_after, release_hour_map, release_day_map, get_reaction, mean, sd)

HDD={dt.date.fromisoformat(k):v for k,v in json.load(open("/home/user/Markets/data/kalshi_hist/cpc_HDD.json")).items()}
CDD={dt.date.fromisoformat(k):v for k,v in json.load(open("/home/user/Markets/data/kalshi_hist/cpc_CDD.json")).items()}
def wksum(mp,d): return sum(mp.get(d-dt.timedelta(days=i),0) or 0 for i in range(7))

REGIMES=["winter-withdrawal (HDD hump)","summer-withdrawal (CDD power-burn hump)",
         "spring-injection (mild shoulder)","fall-injection (mild shoulder)"]
def regime(d):
    h=wksum(HDD,d); c=wksum(CDD,d); w=d.isocalendar()[1]
    if h>120: return REGIMES[0]           # winter-withdrawal, HDD-driven
    if c>40:  return REGIMES[1]           # summer-withdrawal, CDD power-burn
    return REGIMES[2] if w<27 else REGIMES[3]  # spring vs fall shoulder injection

def build():
    surp=seasonal_surprise(weekly_changes(load_eia("eia_ng_storage.json",1.0)))
    rhr=release_hour_map("yh_NG_60m.csv",10); rdy=release_day_map("yh_NG_1d.csv")
    recs=[]
    for d,actual,exp,s in surp:
        rel=next_weekday_after(d,3)
        rh=get_reaction(rhr,rel); rd=get_reaction(rdy,rel)
        if rh is None and rd is None: continue
        recs.append(dict(period=d,change=actual,surprise=s,bull=-s,r_hour=rh,r_day=rd,regime=regime(d)))
    return recs

def stats(recs,rkey):
    out={}
    for reg in REGIMES:
        sub=[x for x in recs if x["regime"]==reg and x[rkey] is not None]
        if len(sub)<10: out[reg]=dict(N=len(sub),note="too few"); continue
        asurp=sorted(abs(x["surprise"]) for x in sub); t1=asurp[len(asurp)//3]
        meaningful=[x for x in sub if abs(x["surprise"])>t1]; nm=len(meaningful)
        hit=sum(1 for x in meaningful if (x["bull"]>0)==(x[rkey]>0))/nm
        conf=sum(1 for x in meaningful if (x["bull"]>0)==(x[rkey]>0)); counter=nm-conf
        stn=sum(1 for x in meaningful if x["bull"]>0 and x[rkey]<0)
        cbull=sum(1 for x in meaningful if x["bull"]>0 and x[rkey]>0)
        bl=[x["bull"] for x in sub]; rc=[x[rkey] for x in sub]; mb,mr=mean(bl),mean(rc)
        cov=sum((b-mb)*(r-mr) for b,r in zip(bl,rc))/(len(sub)-1)
        corr=cov/(sd(bl)*sd(rc)) if sd(bl)*sd(rc)>0 else 0
        out[reg]=dict(N=len(sub),n_meaningful=nm,median_change=round(sorted(x["change"] for x in sub)[len(sub)//2],1),
            mean_abs_reaction=round(mean([abs(x[rkey]) for x in sub]),4),
            directional_hitrate=round(hit,3),hitrate_z=round((hit-0.5)/math.sqrt(0.25/nm),2),
            confirm_vs_counter=f"{conf}:{counter}",sell_the_news_vs_confirm_on_bullish=f"{stn}:{cbull}",
            corr_bull_reaction=round(corr,3))
    return out

if __name__=="__main__":
    recs=build()
    from collections import Counter
    out=dict(event="EIA Natural Gas Storage - DATA-DISCOVERED 4-REGIME split (double-hump demand)",
        contract="KXNATGASD", n_matched=len(recs),
        regime_discovery="per-release weekly degree-days: HDD>120 => winter-withdrawal; CDD>40 => summer-withdrawal(power-burn); else spring/fall injection by ISO week<27. Thresholds from observed humps; reassigns weeks in warm/cold years automatically.",
        regime_counts=dict(Counter(x["regime"] for x in recs)),
        daily_release_day=stats(recs,"r_day"), intraday_release_hour=stats(recs,"r_hour"))
    json.dump(out,open("/home/user/Markets/research/kalshi/hist/natgas_season_results.json","w"),indent=2,default=str)
    print("regime counts:",out["regime_counts"])
    for lens in ("daily_release_day","intraday_release_hour"):
        print(f"\n== {lens} ==")
        for reg,s in out[lens].items():
            if "directional_hitrate" not in s: print(f"  {reg}: {s}"); continue
            print(f"  {reg}\n     N={s['N']} nm={s['n_meaningful']} medChg={s['median_change']} hit={s['directional_hitrate']}(z={s['hitrate_z']}) "
                  f"mean|r|={s['mean_abs_reaction']}% conf:counter={s['confirm_vs_counter']} sellnews:confirm(bull)={s['sell_the_news_vs_confirm_on_bullish']} corr={s['corr_bull_reaction']}")
